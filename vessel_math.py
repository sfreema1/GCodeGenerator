from config import *

class Vessel(object):
	"""docstring for Vessel"""
	def __init__(self, length,thickness,ID=PIPET_OD[PIPET],output_digits=3):
		super(Vessel, self).__init__()
		self.length = length # mm
		self.thickness = thickness # um
		self.ID = ID
		self.output_digits = output_digits
		# calculate vessel volume
		self._calculate_vessel_volume()
		# report necessary volume
		self._report_current_settings()
		# report vessel statistics
		self._report_volume()

	def _calculate_vessel_volume(self):
		""" From Mathematica - Volume of a hollow cylinder
		V = pi*length*wall_thickness*(ID+wall_thickness)
		"""
		thickness = self.thickness/1000. # mm
		self.volume = math.pi*self.length*thickness*(self.ID+thickness)

	def _report_volume(self):
		d = self.output_digits
		msg = "Vessel volume: {:.{digits}f} uL".format(self.volume,digits=d)
		print(msg)

	def _report_current_settings(self):
		d = self.output_digits
		msg = """Printer settings:
		Microstepping: {microstepping}X
		Steps per revolution: {stepsperrev}
		Syringe type: {syringe}
		Syringe ID: {syringediameter} mm
		Syringe cross-section: {syringecrosssection:.{digits}f} uL/mm
		Syringe void volume: {syringevoidvolume} mL
		Tip type: {tip}
		Tip ID: {tipdiameter} mm
		Tip cross-section: {tipcrosssection:.{digits}f} mm^2
		Tip void volume: {tipvoidvolume} mL
		Pipet type: {pipettype}
		Pipet OD: {pipetdiameter} mm
		""".format(digits=d,microstepping=MICROSTEPPING,stepsperrev=STEPS_PER_REVOLUTION,
			syringe=SYRINGE,syringediameter=SYRINGE_CROSS_SECTIONAL_DIAMETER,
			syringecrosssection=SYRINGE_CROSS_SECTIONAL_AREA,syringevoidvolume=SYRINGE_WASTE_SPACE[SYRINGE],
			tip=TIP,tipdiameter=TIP_CROSS_SECTIONAL_DIAMETER,tipcrosssection=TIP_CROSS_SECTIONAL_AREA,
			tipvoidvolume=TIP_VOID_VOLUME[TIP],pipettype=PIPET,pipetdiameter=PIPET_OD[PIPET])
		print(msg)

	def _set_output_digits(self,digits):
		self.output_digits = digits

if __name__ == "__main__":

	vessel = Vessel(16,3000)

