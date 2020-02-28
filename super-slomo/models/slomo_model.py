import numpy as np
import tensorflow as tf

from models import layers


class SloMoNet(tf.keras.Model):
    def __init__(self, n_frames=9, name="SloMoNet", **kwargs):
        super(SloMoNet, self).__init__(name=name, **kwargs)
        self.n_frames = n_frames
        self.t_slices = tf.tile(
            tf.constant(np.linspace(0, 1, n_frames + 2)), [n_frames]
        )
        self.flow_comp_layer = layers.UNet(4, name="flow_comp")
        self.optical_flow = layers.OpticalFlow(name="optical_flow")
        self.output_layer = layers.Output(name="predictions")
        self.warp_layers = [layers.BackWarp()] * 2

    def call(self, inputs, training=False, **kwargs):
        frames_0, frames_1, frames_i = inputs

        frames_i = tf.unstack(frames_i, self.n_frames, axis=1)
        flow_input = tf.concat([frames_0, frames_1], axis=3)
        flow_out = self.flow_comp_layer(flow_input)
        flow_01, flow_10 = flow_out[:, :, :, :2], flow_out[:, :, :, 2:]

        predictions = []
        losses_output = [flow_01, flow_10]
        warp2, warp3 = [], []
        for i in frames_i:

            # extract frame t coefficient
            t_indices = tf.gather(self.t_slices, i)
            t_indices = tf.cast(t_indices, dtype=tf.float32)
            t_indices = t_indices[:, tf.newaxis, tf.newaxis, tf.newaxis]

            optical_input = [frames_0, frames_1, flow_01, flow_10, t_indices]
            f_t0, v_t0, f_t1, v_t1, g_i0_ft0, g_i1_ft1 = self.optical_flow(
                optical_input
            )
            preds_input = [frames_0, f_t0, v_t0, frames_1, f_t1, v_t1, t_indices]
            predictions.append(self.output_layer(preds_input))

            warp2.append(g_i0_ft0)
            warp3.append(g_i1_ft1)

        warp0 = self.warp_layers[0]([frames_1, flow_01])
        warp1 = self.warp_layers[1]([frames_0, flow_10])
        # prepare for output shape
        warp2 = tf.transpose(tf.stack(warp2), [1, 0, 2, 3, 4])
        warp3 = tf.transpose(tf.stack(warp3), [1, 0, 2, 3, 4])
        predictions = tf.transpose(tf.stack(predictions), [1, 0, 2, 3, 4])

        losses_output += [warp0, warp1, warp2, warp3]
        return predictions, losses_output
