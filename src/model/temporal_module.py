"""DSTE 时空激励模块 —— LSTE + GSTE"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math


class h_sigmoid(nn.Module):
    def __init__(self, inplace=True):
        super(h_sigmoid, self).__init__()
        self.relu = nn.ReLU6(inplace=inplace)

    def forward(self, x):
        return self.relu(x + 3) / 6


class h_swish(nn.Module):
    def __init__(self, inplace=True):
        super(h_swish, self).__init__()
        self.sigmoid = h_sigmoid(inplace=inplace)

    def forward(self, x):
        return x * self.sigmoid(x)


class CoordAtt(nn.Module):
    """坐标注意力（LSTE 核心组件）"""
    def __init__(self, inp, oup, reduction=4):
        super(CoordAtt, self).__init__()
        self.pool_h = nn.AdaptiveAvgPool2d((None, 1))
        self.pool_w = nn.AdaptiveAvgPool2d((1, None))
        mip = max(8, inp // reduction)
        self.conv1 = nn.Conv2d(inp, mip, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(mip)
        self.act = h_swish()
        self.conv_h = nn.Conv2d(mip, oup, kernel_size=1, bias=False)
        self.conv_w = nn.Conv2d(mip, oup, kernel_size=1, bias=False)

    def forward(self, x):
        identity = x
        n, c, h, w = x.size()
        x_h = self.pool_h(x)
        x_w = self.pool_w(x).permute(0, 1, 3, 2)
        y = torch.cat([x_h, x_w], dim=2)
        y = self.conv1(y)
        y = self.bn1(y)
        y = self.act(y)
        x_h, x_w = torch.split(y, [h, w], dim=2)
        x_w = x_w.permute(0, 1, 3, 2)
        a_h = self.conv_h(x_h).sigmoid()
        a_w = self.conv_w(x_w).sigmoid()
        out = identity * a_w * a_h
        return out


class SpatialAttention(nn.Module):
    """空间自注意力（GSTE 核心组件）"""
    def __init__(self, in_channels):
        super(SpatialAttention, self).__init__()
        self.norm = nn.GroupNorm(1, in_channels)
        self.q = nn.Conv2d(in_channels, in_channels, kernel_size=1, bias=False, groups=in_channels)
        self.k = nn.Conv2d(in_channels, in_channels, kernel_size=1, bias=False, groups=in_channels)
        self.v = nn.Conv2d(in_channels, in_channels, kernel_size=1, bias=False, groups=in_channels)
        self.scaler = in_channels ** -0.5
        self.softmax = nn.Softmax(-1)
        self.dropout = nn.Dropout(0.1)

    def forward(self, x):
        identity = x
        n, c, t, h, w = x.size()
        x = x[:, :, 1:, :, :] - x[:, :, :-1, :, :]
        x = torch.mean(x, dim=2)
        x = self.norm(x)
        q = self.q(x).view(n, c, -1).permute(0, 2, 1).contiguous()
        k = self.k(x).view(n, c, -1)
        v = self.v(x).view(n, c, -1).permute(0, 2, 1).contiguous()
        attn = torch.matmul(q, k) * self.scaler
        attn = self.dropout(self.softmax(attn))
        attn = torch.matmul(attn, v)
        attn = torch.mean(attn, dim=2)
        attn = attn.view(n, 1, 1, h, w)
        return identity + identity * attn


class TemporalModule(nn.Module):
    """DSTE 模块：LSTE + GSTE"""
    def __init__(self, net, n_segment, n_div):
        super(TemporalModule, self).__init__()
        self.net = net
        self.n_segment = n_segment
        self.n_div = n_div
        self.in_channels = net.in_channels
        self.num_shift_channel = int(self.in_channels * self.n_div)
        if self.num_shift_channel != 0:
            self.split_sizes = [self.num_shift_channel, self.in_channels - self.num_shift_channel]
            self.conv_th = nn.Sequential(
                nn.Conv2d(self.num_shift_channel, self.num_shift_channel,
                          kernel_size=3, padding=1, groups=self.num_shift_channel, bias=False),
                nn.BatchNorm2d(self.num_shift_channel),
                nn.ReLU(inplace=True)
            )
            self.conv_tw = nn.Sequential(
                nn.Conv2d(self.num_shift_channel, self.num_shift_channel,
                          kernel_size=3, padding=1, groups=self.num_shift_channel, bias=False),
                nn.BatchNorm2d(self.num_shift_channel),
                nn.ReLU(inplace=True)
            )
            self.att_th = CoordAtt(self.num_shift_channel, self.num_shift_channel)
            self.att_tw = CoordAtt(self.num_shift_channel, self.num_shift_channel)
        self.spatial_attention = SpatialAttention(self.in_channels)

    def forward(self, x):
        nt, c, h, w = x.size()
        n_batch = nt // self.n_segment
        if self.num_shift_channel != 0:
            x = x.view(n_batch, self.n_segment, c, h, w).transpose(1, 2).contiguous()
            x = list(x.split(self.split_sizes, dim=1))
            # LSTE: H 方向
            x1 = x[0].permute(0, 4, 1, 2, 3).contiguous()
            x1 = x1.view(n_batch * w, self.num_shift_channel, self.n_segment, h)
            x1 = self.att_th(x1)
            x1 = self.conv_th(x1)
            x1 = x1.view(n_batch, w, self.num_shift_channel, self.n_segment, h)
            x1 = x1.permute(0, 2, 3, 4, 1).contiguous()
            # LSTE: W 方向
            x2 = x[0].permute(0, 3, 1, 2, 4).contiguous()
            x2 = x2.view(n_batch * h, self.num_shift_channel, self.n_segment, w)
            x2 = self.att_tw(x2)
            x2 = self.conv_tw(x2)
            x2 = x2.view(n_batch, h, self.num_shift_channel, self.n_segment, w)
            x2 = x2.permute(0, 2, 3, 1, 4).contiguous()
            x[0] = x1 + x2
            x = torch.cat(x, dim=1)
        x = self.spatial_attention(x)
        x = x.transpose(1, 2).contiguous().view(nt, c, h, w)
        return self.net(x)


def make_temporal_module(net, n_segment, n_div=8, place='blockres', temporal_pool=False):
    """将 DSTE 模块插入 ResNet 各层的残差块"""
    if temporal_pool:
        n_segment_list = [n_segment, n_segment // 2, n_segment // 2, n_segment // 2]
    else:
        n_segment_list = [n_segment] * 4
    assert n_segment_list[-1] > 0
    print('=> n_segment per stage: {}'.format(n_segment_list))
    import torchvision
    if isinstance(net, torchvision.models.ResNet):
        if 'blockres' in place:
            n_round = 1
            if len(list(net.layer3.children())) >= 23:
                n_round = 2
            def make_block_temporal(stage, this_segment):
                blocks = list(stage.children())
                for i, b in enumerate(blocks):
                    if i % n_round == 0:
                        blocks[i].conv1 = TemporalModule(b.conv1, n_segment=this_segment, n_div=n_div)
                return nn.Sequential(*blocks)
            net.layer1 = make_block_temporal(net.layer1, n_segment_list[0])
            net.layer2 = make_block_temporal(net.layer2, n_segment_list[1])
            net.layer3 = make_block_temporal(net.layer3, n_segment_list[2])
            net.layer4 = make_block_temporal(net.layer4, n_segment_list[3])


class TemporalPool(nn.Module):
    def __init__(self, net, n_segment):
        super(TemporalPool, self).__init__()
        self.net = net
        self.n_segment = n_segment

    def forward(self, x):
        nt, c, h, w = x.size()
        n_batch = nt // self.n_segment
        x = x.view(n_batch, self.n_segment, c, h, w).transpose(1, 2)
        x = F.max_pool3d(x, kernel_size=(3, 1, 1), stride=(2, 1, 1), padding=(1, 0, 0))
        x = x.transpose(1, 2).contiguous().view(nt // 2, c, h, w)
        return self.net(x)
