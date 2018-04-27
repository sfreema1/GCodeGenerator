from config import *

# In config.py, make sure tip and syringe selections match what you are using

#define the G object
class G(object):
	def __init__(self,output_digits=4,num_extruder=1,initial_feedrate=100.0,include_header=True):
		"""
		Parameters
		-----------
		output_digits : int (default: 6)
			How many digits to include after decimal in output gcode
		num_extruder : int (default: 1)
			How many extruders are equipped on the machine
		initial_feedrate : float  (default: 100.0)
			The starting feedrate of the printer (in mm/min)
		header : bool (default: True)
			If true, will display the header at the top of the Gcode
		"""
		self.output_digits = output_digits
		self.num_extruder = num_extruder
		self.speed = initial_feedrate
		self.include_header = include_header

		###===== Internal variables =====###
		self.mm_to_steps = dict(zip(AXES,DEFAULT_AXIS_STEPS_PER_MM))
		self.steps_to_mm = dict(zip(AXES,MM_PER_STEP))
		self._current_position = dict(zip(AXES,[0,0,0,0]))
		self.position_history = dict(zip(AXES,([0],[0],[0],[0]))) # in steps
		self.travel_distance = 0 # mm
		self.extrusion_distance = 0 # mm
		self.max_e_position = 0 # in steps
		self.extrusion_volume = 0 # uL
		self.print_time = 0 # seconds
		self.is_relative = True # relative or absolute positioning
		self.extrusionrate_constant = False # if true, extrusion rate will always be kept the same

		# run setup method
		self.setup()

	# ---------- PRIVATE METHODS ---------- #
	def _get_position(self,axis,mode='steps'):
		if mode == 'steps':
			return self._current_position[axis]
		elif mode == 'mm':
			return self._current_position[axis]*self.steps_to_mm[axis]

	def _update_current_position(self,x=None,y=None,z=None,e=None,**kwargs):
		# redirect input values from command
		dims = {}
		if x is not None:
			dims[AXES[0]] = x
		if y is not None:
			dims[AXES[1]] = y
		if z is not None:
			dims[AXES[2]] = z
		if e is not None:
			dims[AXES[3]] = e

		xyzdistance = 0.0 # distance of move
		edistance = 0.0 # distance of extrusion

		for axes in dims.keys():
			destination = dims[axes] + self._get_position(axes,'mm') if self.is_relative else dims[axes]
			target = int(round(destination*self.mm_to_steps[axes]))
			diff = target - self._get_position(axes)
			if axes is not AXES[3]:
				xyzdistance += (diff*self.steps_to_mm[axes])**2
			else:
				edistance = abs(diff*self.steps_to_mm[axes])
				if axes is AXES[3] and target > self.max_e_position:
					ediff = target - self.max_e_position
					extruded_volume = ediff*self.steps_to_mm[axes]*SYRINGE_CROSS_SECTIONAL_AREA # uL
					self.extrusion_volume += extruded_volume
					self.max_e_position = target

			self._current_position[axes] += diff

		# calculate Euclidean distance
		xyzdistance = math.sqrt(xyzdistance)
		# calculate move time 
		if xyzdistance != 0.0:
			move_time = 60.*xyzdistance/self.speed
			if edistance != 0.0:
				espeed = 60.*edistance/move_time # mm/min
				flowrate = espeed*SYRINGE_CROSS_SECTIONAL_AREA/60. # uL/s
				print(";Extrusion rate: {} mm/min | Flow rate: {} uL/s".format(espeed,flowrate))
		elif xyzdistance == 0.0 and edistance != 0.0:
			move_time = 60.*edistance/self.speed
			espeed = 60.*edistance/move_time # mm/min
			flowrate = espeed*SYRINGE_CROSS_SECTIONAL_AREA/60. # uL/s
			print(";Extrusion rate: {} mm/min | Flow rate: {} uL/s".format(espeed,flowrate))
		self.print_time += move_time

		# update travel distance 
		if xyzdistance != 0.0:
			# add xyzdistance to travel distance
			self.travel_distance += xyzdistance
		if edistance != 0.0:
			# add edistance to extrusion distance
			self.extrusion_distance += edistance
		
		# record position
		for axes in AXES:
			self.position_history[axes].append(self._current_position[axes])

	def _format_args(self,x,y,z,e,**kwargs):
		d = self.output_digits
	 	args = []
	 	# Look for passed kwargs representing the axes
	 	if x is not None:
	 		args.append('{0}{1:.{digits}f}'.format('X',x,digits=d))
	 	if y is not None:
	 		args.append('{0}{1:.{digits}f}'.format('Y',y,digits=d))
	 	if z is not None:
	 		args.append('{0}{1:.{digits}f}'.format('Z',z,digits=d))
	 	if e is not None:
	 		args.append('{0}{1:.{digits}f}'.format('E',e,digits=d))
	 	args += ['{0}{1:.{digits}f}'.format(k,kwargs[k],digits=d) for k in sorted(kwargs)]
	 	# Join them all together
	 	args = ' '.join(args)
	 	return args

	# ---------- UI METHODS ---------- #
	def write(self,statement_in):
		print(statement_in)

	def move(self,x=None,y=None,z=None,e=None,extrusionunit='mm'):
		# Calculate extrusion distance from volume if applicable
		if e is not None:
			if extrusionunit == 'uL' or extrusionunit == 'ul':
				e = e/SYRINGE_CROSS_SECTIONAL_AREA # mm
		# Update internal tracking variables
		self._update_current_position(x,y,z,e)
		args = self._format_args(x,y,z,e)
		cmd = 'G1 '+ args
		# Print the line
		self.write(cmd)

	def circular_move(self,radius,axis='+X',e=None,extrusionunit='mm',direction='CW'):
		if ('X' not in axis) and ('Y' not in axis):
			raise RuntimeError('Axis of circular move not indicated.')
		if ('+' not in axis) and ('-' not in axis):
			raise RuntimeError('Positive or negative not indicated.')
		# Change to relative positioning if not already since this function only works
		# with relative position
		changed_positioning = False
		if self.is_relative == False:
			self.relative() # change to relative
			changed_positioning = True # flag to change back later

		self.write(";Circular path -> Dir: {} | D: {} mm | C: {} mm".format(axis,2*radius,2*radius*math.pi))
		# Calculate extrusion distance from volume if applicable
		if e is not None:
			if extrusionunit == 'uL' or extrusionunit == 'ul':
				e = e/SYRINGE_CROSS_SECTIONAL_AREA # mm
		# The printer currently does not have a retract function
		# Extruded material cannot be retracted.
		# For these two reasons above, the below must be executed for tracking amount of volume used.
		# If e_move is negative, it should not add to total volume extruded
		# If e_move does not add to the current e_position 
		if e is not None:
			axes = EXTRUSION_AXES[0]
			destination = e + self._get_position(axes,'mm') if self.is_relative else e
			target = int(round(destination*self.mm_to_steps[axes]))
			diff = target - self._get_position(axes)
			edistance = abs(diff*self.steps_to_mm[axes])
			self.extrusion_distance += edistance
			if target > self.max_e_position:
				ediff = target - self.max_e_position
				extruded_volume = ediff*self.steps_to_mm[axes]*SYRINGE_CROSS_SECTIONAL_AREA # uL
				self.extrusion_volume += extruded_volume
				self.max_e_position = target
			self._current_position[axes] += diff

		# Add XYX displacement to total distance
		xydistance = 2*math.pi*radius # should be updated later to account for discrete movement
		self.travel_distance += xydistance
		move_time = 60.*xydistance/self.speed
		if edistance != 0.0:
			espeed = 60.*edistance/move_time # mm/min
			flowrate = espeed*SYRINGE_CROSS_SECTIONAL_AREA/60. # uL/s
			print(";Extrusion rate: {} mm/min | Flow rate: {} uL/s".format(espeed,flowrate))
		self.print_time += move_time

		# Figure out direction to make circle
		if "+" in axis:
			r = radius
		elif "-" in axis:
			r = -radius
		if "X" in axis:
			kwin = {"I":r}
		elif "Y" in axis:
			kwin = {"J":r}
		# Choose the correct G command to complete the move
		if direction == 'CW':
			cmd = 'G2 '
		elif direction == 'CCW':
			cmd = 'G3 '
		# Format the move
		args = self._format_args(x=None,y=None,z=None,e=e,**kwin)
		# Write command
		cmd += args
		self.write(cmd)

		# record position
		for axes in AXES:
			self.position_history[axes].append(self._current_position[axes])

		# change back to absolute positioning if that's what was being used.
		if changed_positioning:
			self.absolute()

	def set_feedrate(self,rate,extrusionunit='mm'):
		""" Set the feed rate (tool head speed) in mm/min

		Parameters
		----------
		rate : float
			The speed to move the tool head in mm/min
		extrusionunit : 'mm/min' or 'uL/min' or 'uL'
		"""
		d = self.output_digits
		self.write('G1 F{:.{digits}f}'.format(rate,digits=d))
		self.speed = rate

	def relative(self):
		self.write('G91')
		self.is_relative = True

	def absolute(self):
		self.write('G90')
		self.is_relative = False

	def allow_cold_extrusion(self,mode=True):
		msg = 'M302 P'
		if mode == True:
			msg += '1'
		else:
			msg += '0'
		self.write(msg)

	def set_axis_steps_per_mm(self,x=None,y=None,z=None,e=None,comment=None):
		if x is not None:
			self.mm_to_steps[AXES[0]] = x
		if y is not None:
			self.mm_to_steps[AXES[1]] = y
		if z is not None:
			self.mm_to_steps[AXES[2]] = z
		if e is not None:
			self.mm_to_steps[AXES[3]] = e

		args = self._format_args(x,y,z,e)
		cmd = 'M92 '+args

		if comment is not None:
			com = ' ;' + comment
			cmd += com

		# Print the line
		self.write(cmd)

	# ---------- G-Code COMMENT METHODS --------- #

	def print_blank_line(self):
		print(' ')

	def setup(self):
		if self.include_header:
			self.header()
		self.write('')

	def header(self):
		self.write(';Printer is using {}X microstepping'.format(MICROSTEPPING))
		self.write(';There are {} steps per revolution of the motor.'.format(STEPS_PER_REVOLUTION))
		args = [axes+str(1000.*self.steps_to_mm[axes]) for axes in AXES]
		args = ' '.join(args)
		self.write(';Min. travel/extrusion distance (um): '+args)
		self.write(';Syringe type: {}'.format(SYRINGE))
		self.write(';Syringe waste volume (mL): {}'.format(SYRINGE_WASTE_SPACE[SYRINGE]))
		self.write(';Min. extrudable volume (uL): {}'.format(self.steps_to_mm[AXES[3]]*SYRINGE_CROSS_SECTIONAL_AREA))
		self.write(';Tip type: {}'.format(TIP))
		self.write(';Tip diameter (mm): {}'.format(TIP_CROSS_SECTIONAL_DIAMETER))
		self.write(';Tip void volume (mL): {}'.format(TIP_VOID_VOLUME[TIP]))
		self.write(';Volumetric flow: {} uL/min for every 100 mm/min'.format(100*SYRINGE_CROSS_SECTIONAL_AREA))
		self.write(';For syringe extrusion rate of 100 mm/min, tip extrusion rate is {} mm/min'.format(100.0*SYRINGE_CROSS_SECTIONAL_AREA/TIP_CROSS_SECTIONAL_AREA))

	def summary_report(self):
		self.write('')
		self.report_current_location()
		self.report_distances()
		self.report_extrusion_volume()
		self.report_print_time()

	def report_current_location(self):
		d = self.output_digits
		args = []
		for axes in AXES:
			pos = self._get_position(axes,'mm')
			args.append('{0}{1:.{digits}f}'.format(axes,pos,digits=d))
		args = ' '.join(args)
		msg = ';Current location (mm): ' + args
		print(msg)

	def report_distances(self):
		d = self.output_digits
		msg1 = ';Total travel distance: {:.{digits}f} mm'.format(self.travel_distance,digits=d)
		msg2 = ';Total extrusion distance: {:.{digits}f} mm'.format(self.extrusion_distance,digits=d)
		self.write(msg1)
		self.write(msg2)

	def report_extrusion_volume(self):
		d = self.output_digits
		msg = ';Total extruded volume: {} uL'.format(self.extrusion_volume)
		self.write(msg)

	def report_print_time(self):
		msg = ';Total print time: '

		if self.print_time > 60.0:
			minutes,seconds = divmod(self.print_time,60.0)
			time_report = '{0} min {1:.{digits}f} s'.format(int(minutes),seconds,digits=self.output_digits)
		else:
			time_report = '{0:.{digits}f} s'.format(self.print_time,digits=self.output_digits)

		msg += time_report
		self.write(msg)

# ========== Cartesian shape functions ========== #
	def print_disc(self,r2,r1,step,thickness):
		num_ring = int(1+(r2-r1)/step)
		step_list = [step*i for i in range(num_ring)]
		radii = [r2-i for i in step_list]
		circums = [2*math.pi*r for r in radii]
		total_path_length = sum(circums)
		weights = [i/total_path_length for i in circums] # in mm
		# now calculate total volume
		vol = math.pi*thickness*((r2**2) - (r1**2))
		# calculate e move
		total_e = vol/SYRINGE_CROSS_SECTIONAL_AREA
		e_list = [total_e*i for i in weights]
		# plan for move
		for i in range(num_ring):
			self.circular_move(radii[i],e=e_list[i])
			if i != (num_ring-1):
				self.move(x=step)

# ========== Vessel functions ========== #
	def print_vessel(self,length,thickness):
		pass

		
if __name__ == "__main__":
	g = G()
	g.set_feedrate(100)
	g.move(y=50,x=50)
	g.print_blank_line()
	g.print_disc(6,2,1,0.3)
	g.summary_report()
