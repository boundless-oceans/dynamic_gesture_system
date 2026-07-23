"""TSN 模型定义（ResNet-50 + DSTE 模块）"""

import torch
import torch.nn as nn
import torchvision
from torch.nn.init import normal_, constant_

from src.model.basic_ops import ConsensusModule
from src.model.temporal_module import make_temporal_module


class TSN(nn.Module):
    """Temporal Segment Network with DSTE module"""

    def __init__(self, num_class, num_segments, modality='RGB',
                 base_model='resnet50', consensus_type='avg',
                 dropout=0.5, img_feature_dim=256,
                 is_shift=True, shift_div=4, shift_place='blockres',
                 temporal_pool=False, non_local=False):
        super(TSN, self).__init__()
        self.modality = modality
        self.num_segments = num_segments
        self.reshape = True
        self.before_softmax = True
        self.dropout = dropout
        self.consensus_type = consensus_type
        self.img_feature_dim = img_feature_dim
        self.is_shift = is_shift
        self.shift_div = shift_div
        self.shift_place = shift_place
        self.base_model_name = base_model
        self.temporal_pool = temporal_pool
        self.non_local = non_local
        self.new_length = 1 if modality == 'RGB' else 5

        self._prepare_base_model(base_model)
        feature_dim = self._prepare_tsn(num_class)
        self.consensus = ConsensusModule(consensus_type)

    def _prepare_tsn(self, num_class):
        feature_dim = getattr(self.base_model, self.base_model.last_layer_name).in_features
        if self.dropout == 0:
            setattr(self.base_model, self.base_model.last_layer_name, nn.Linear(feature_dim, num_class))
            self.new_fc = None
        else:
            setattr(self.base_model, self.base_model.last_layer_name, nn.Dropout(p=self.dropout))
            self.new_fc = nn.Linear(feature_dim, num_class)
        std = 0.001
        if self.new_fc is None:
            normal_(getattr(self.base_model, self.base_model.last_layer_name).weight, 0, std)
            constant_(getattr(self.base_model, self.base_model.last_layer_name).bias, 0)
        else:
            normal_(self.new_fc.weight, 0, std)
            constant_(self.new_fc.bias, 0)
        return feature_dim

    def _prepare_base_model(self, base_model):
        if 'resnet' in base_model:
            self.base_model = getattr(torchvision.models, base_model)(weights=None)
            if self.is_shift:
                print('Adding DSTE temporal module...')
                make_temporal_module(self.base_model, self.num_segments,
                                     n_div=self.shift_div, place=self.shift_place,
                                     temporal_pool=self.temporal_pool)
            if self.non_local:
                from src.model.non_local import make_non_local
                make_non_local(self.base_model, self.num_segments)
            self.base_model.last_layer_name = 'fc'
            self.input_size = 224
            self.input_mean = [0.485, 0.456, 0.406]
            self.input_std = [0.229, 0.224, 0.225]
            self.base_model.avgpool = nn.AdaptiveAvgPool2d(1)
        else:
            raise ValueError('Unknown base model: {}'.format(base_model))

    def forward(self, input):
        # input: (batch, 3*num_segments, H, W)
        sample_len = 3 * self.new_length
        if self.modality == 'RGB':
            sample_len = 3
            input = input.view((-1, self.num_segments, sample_len) + input.size()[-2:])
            input = input.view((-1,) + input.size()[-3:])  # (batch*segments, 3, H, W)
        base_out = self.base_model(input)  # (batch*segments, feature_dim)
        if self.new_fc is not None:
            base_out = self.new_fc(base_out)
        base_out = base_out.view((-1, self.num_segments, base_out.size(-1)))
        output = self.consensus(base_out).squeeze(1)  # (batch, num_class)
        return output

    @property
    def crop_size(self):
        return self.input_size

    @property
    def scale_size(self):
        return self.input_size * 256 // 224
