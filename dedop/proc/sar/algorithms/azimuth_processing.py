import numpy as np
from numpy.linalg import norm
from math import cos
from enum import Enum

from ..base_algorithm import BaseAlgorithm


class AzimuthProcessingMethods(Enum):
    """
    Enum for azimuth processing method selection flag
    """

    dynamic = 0
    approximate = 1
    exact = 2


class AzimuthWeighting(Enum):
    """
    Enum for azimuth weighting toggle flag
    """

    enabled = 1
    disabled = 0


class AzimuthProcessingAlgorithm(BaseAlgorithm):
    """
    class for performing the Azimuth Processing Algorithm
    """
    def __init__(self, chd, cst):
        super().__init__(chd, cst)

        self.beams_focused = None

    def __call__(self, isp, wavelength_ku, method=AzimuthProcessingMethods.dynamic,
                 weighting=AzimuthWeighting.disabled):
        """
        Executes the azimuth processing algorithm

        :param isp: The InstrumentSourcePacket instance
        :param wavelength_ku: The signal wavelength
        :param method: The method to use
        :param weighting: Azimuth weighting flag
        """
        self.beams_focused = np.empty(
            isp.waveform_cor_sar.shape,
            dtype=np.complex128
        )

        if weighting == AzimuthWeighting.enabled:
            # TODO: perform azimuth weighting
            pass

        # azimuth processing with surface dependant method
        if method == AzimuthProcessingMethods.dynamic:
            # TODO: change method based on surface
            self.compute_approximate_method(isp, wavelength_ku)

        # azimuth processing with approx. method
        elif method == AzimuthProcessingMethods.approximate:
            self.compute_approximate_method(isp, wavelength_ku)
        # azimuth processing with exact method
        elif method == AzimuthProcessingMethods.exact:
            self.compute_exact_method(isp, wavelength_ku)

    def compute_approximate_method(self, isp, wavelength_ku):
        """
        Azimuth processing approximate method

        the azimuth processing is done only once, using the beam
        angle phase of the beam pointing to the nadir (considered
        the central beam)

        :param isp: InstrumentSourcePacket instance
        :param wavelength_ku: signal wavelength
        """
        # find the nadir beam angle
        nadir_beam_angle = self.get_nadir_beam_angle(isp)

        # use the nadir beam angle to compute the phase shift
        wfm_phase_shift = self.compute_phase_shift(
            isp, nadir_beam_angle, wavelength_ku
        )
        # compute the azimuth FFTs
        wfm_fft_azimuth = self.compute_fft_azimuth_dimension(
            wfm_phase_shift
        )

        # the result is the focused beams. If the list of beam angles
        # is increasing in size, then the useful first beams are in the
        # output of the waveform_fft_azimuth (because the first part of the
        # waveform_fft_azimuth beams point to surfaces that are before the
        # first surface). This way we will always have the beams in the same
        # position as the corresponding beam angle in the beam angle/surfaces
        # seen lists.
        if isp.beam_angles_trend == 1:
            beams_offset = self.chd.n_ku_pulses_burst -\
                           len(isp.beam_angles_list)
        else:
            beams_offset = 0
        copy_end = self.chd.n_ku_pulses_burst - beams_offset
        self.beams_focused[:copy_end, :] = wfm_fft_azimuth[beams_offset:, :]

    def compute_exact_method(self, isp, wavelength_ku):
        """
        Azimuth processing exact method

        The azimuth processing is performed for each surface seen,
        and the beam angle at each surface is used to compute the phase
        shift. The central beam of the result of the FFT is used, and
        placed in the array position corresponding to the beam angle
        from which it was computed.

        :param isp: InstrumentSourcePacket
        :param wavelength_ku: signal wavelength
        """
        for beam_index, beam_angle_value in enumerate(isp.beam_angles_list):
            # calculate the shape shift based upon the current
            # beam angle
            wfm_phase_shift = self.compute_phase_shift(
                isp, beam_angle_value, wavelength_ku
            )
            # calculate the FFT of the current beam
            wfm_fft_azimuth = self.compute_fft_azimuth_dimension(
                wfm_phase_shift
            )
            # insert the central beam of the result into the same
            # position as the beam angle in the beam angle/surface seen
            # lists (this way the beams can be easily matched to surfaces)
            self.beams_focused[beam_index, :] =\
                wfm_fft_azimuth[self.chd.n_ku_pulses_burst // 2, :]

    def compute_phase_shift(self, isp, beam_angle, wavelength_ku):
        """
        For each pulse of the burst, a phase (based on the given beam
        angle value) is applied to the waveform

        :param isp: the current InstrumentSourcePacket
        :param beam_angle: the input beam angle
        :param wavelength_ku: the signal wavelength

        :return waveform_phase_shift: the phase shifted waveform
        """
        # create empty output array
        waveform_phase_shift = np.empty(
            isp.waveform_cor_sar.shape,
            dtype=np.complex128
        )


        for pulse_index in range(self.chd.n_ku_pulses_burst):
            beam_angle_phase = np.exp(-2j * 2. * self.cst.pi / wavelength_ku *
                                      norm(isp.vel_sat_sar) * cos(beam_angle) *
                                      isp.pri_sar_pre_dat * pulse_index)
            waveform_phase_shift[pulse_index, :] =\
                beam_angle_phase * isp.waveform_cor_sar[pulse_index, :]

        return waveform_phase_shift

    def compute_fft_azimuth_dimension(self, waveform_phase_shift):
        """
        :param waveform_phase_shift: the phase shifted waveform to transform

        :return waveform_fft_azimuth: The shifted FFT along the azimuth direction
        """
        # compute the FFT along the azimuth dimension,
        # and apply orthogonal normalization to the result
        out_fft = np.fft.fft(
            waveform_phase_shift,
            axis=0, norm='ortho'
        )
        # return the shifted FFT values
        return np.fft.fftshift(
            out_fft, axes=0
        )

    def get_nadir_beam_angle(self, isp):
        """
        :param isp: The InstrumentSourcePacket to be processed

        :return: nadir_beam_angle
        """
        beam_angles_list_size = len(isp.beam_angles_list)
        half_pulses = self.chd.n_ku_pulses_burst // 2

        # if the beam angles list is not full (64), and the trend indicates
        # that the size is increasing, the nadir beam is first of the last 'half_pulses'
        # (or the first if are less than 'half_pulses' elements
        if isp.beam_angles_trend == 1:
            # if there aren't enough elements, pick the first one
            if beam_angles_list_size < half_pulses:
                nadir_beam_index = 0
            # otherwise, get first of the last 'half_pulses'
            else:
                nadir_beam_index = -half_pulses

        # if the mbeam angles list is not full (64), and the trend indicates
        # that the size is decreasing, the nadir beam is the 33rd (or the last
        # if there are less than 33 elements)
        elif isp.beam_angles_trend == -1:
            # if there aren't enough elements, pick the last one
            if beam_angles_list_size <= half_pulses:
                nadir_beam_index = -1
            # otherwise, get the last of the first 'half_pulses'
            else:
                nadir_beam_index = half_pulses
        # if the beam angles list is full, the nadir beam is the 33rd one
        elif isp.beam_angles_trend == 0:
            nadir_beam_index = half_pulses
        # check for invalid trend directions
        else:
            raise Exception(
                "Beam Angle Trend must be in {-1, 0, 1}"
            )

        # after the index has been selected, get the corresponding beam angle
        nadir_beam_angle = isp.beam_angles_list[nadir_beam_index]
        return nadir_beam_angle
