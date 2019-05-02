# coding: utf-8
import torch
from torch import nn
from math import sqrt

from layers.style_encoder import GlobalStyleTokens
from layers.tacotron import Prenet, Encoder, Decoder, PostCBHG
from utils.generic_utils import sequence_mask


class Tacotron(nn.Module):
    def __init__(self,
                 num_chars,
                 linear_dim=1025,
                 mel_dim=80,
                 r=5,
                 padding_idx=None,
                 memory_size=5,
                 attn_win=False,
                 attn_norm="sigmoid"):
        super(Tacotron, self).__init__()
        self.r = r
        self.mel_dim = mel_dim
        self.linear_dim = linear_dim
        self.embedding = nn.Embedding(num_chars, 256, padding_idx=padding_idx)
        self.embedding.weight.data.normal_(0, 0.3)
        self.encoder = Encoder(256)
        self.decoder = Decoder(256, mel_dim, r, memory_size, attn_win, attn_norm)
        self.postnet = PostCBHG(mel_dim)
        self.last_linear = nn.Sequential(
            nn.Linear(self.postnet.cbhg.gru_features * 2, linear_dim),
            nn.Sigmoid())
        self.global_style_tokens = GlobalStyleTokens(mel_dim, 8, 10,
                                                     256, 128)

    def forward(self, characters, text_lengths, mel_specs):
        B = characters.size(0)
        mask = sequence_mask(text_lengths).to(characters.device)
        inputs = self.embedding(characters)
        encoder_outputs = self.encoder(inputs)
        style_encoding = self.global_style_tokens(mel_specs)
        style_encoding = style_encoding.expand(-1, encoder_outputs.size(1),
                                               -1)
        encoder_outputs = encoder_outputs + style_encoding
        mel_outputs, alignments, stop_tokens = self.decoder(
            encoder_outputs, mel_specs, mask)
        mel_outputs = mel_outputs.view(B, -1, self.mel_dim)
        linear_outputs = self.postnet(mel_outputs)
        linear_outputs = self.last_linear(linear_outputs)
        return mel_outputs, linear_outputs, alignments, stop_tokens

    def inference(self, characters):
        B = characters.size(0)
        inputs = self.embedding(characters)
        encoder_outputs = self.encoder(inputs)
        mel_outputs, alignments, stop_tokens = self.decoder.inference(
            encoder_outputs)
        mel_outputs = mel_outputs.view(B, -1, self.mel_dim)
        linear_outputs = self.postnet(mel_outputs)
        linear_outputs = self.last_linear(linear_outputs)
        return mel_outputs, linear_outputs, alignments, stop_tokens