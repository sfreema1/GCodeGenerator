from config import *

"""
#### CHANGE LOG ####
4/28/2018 - Changed where syringe type and tip type are chosen. Now user selects that when creating G object

5/10/2018 - Fixed set_axis_steps_per_mm() function
"""

#define the G object
class G(object):
	def __init__(self,microstepping=MICROSTEPPING,output_digits=4,num_extruder=1,initial_feedrate=100.0,include_header=True,syringe="BD-1ml",tip="JG24-1.25TTX",layer_height=0.3):
		"""
		Parameters
		-----------
		microstepping : int (default: 16)
			What to multiply the original steps/revolution for motors
		output_digits : int (default: 6)
			How many digits to include after decimal in output gcode
		num_extruder : int (default: 1)
			How many extruders are equipped on the machine
		initial_feedrate : float  (default: 100.0)
			The starting feedrate of the printer (in mm/min)
		header : bool (default: True)
			If true, will display the header at the top of the Gcode
		"""
		self.microstepping = microstepping
		self.output_digits = output_digits
		self.num_extruder = num_extruder
		self.speed = initial_feedrate
		self.layer_height = layer_height
		self.include_header = include_header
		# Extrusion calculations
		self.steps_per_rev = int(self.microstepping*360/MOTOR_STEP_ANGLE)
		self.syringe = syringe
		self.syringe_diameter = SYRINGE_DIAMETER[self.syringe] # mm
		self.syringe_cross_section = math.pi*(self.syringe_diameter/2)**2 # mm
		self.tip = tip
		self.tip_ID = TIP_ID[self.tip]
		self.tip_cross_section = math.pi*(self.tip_ID/2)**2
		# Waste volume
		self.waste_volume = SYRINGE_WASTE_SPACE[self.syringe] + TIP_VOID_VOLUME[self.tip]

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
		self.allow_cold_extrusion = None # if true, allows E moves to occur

		# run setup method
		self.setup()

	# ---------- PRIVATE METHODS ---------- #
	def _get_position(self,axis,mode='steps'):
		if mode == 'steps':
			return self._current_position[axis]
		elif mode == 'mm':
			return self._current_position[axis]*self.steps_to_mm[axis]

	def _update_current_position(self,x=None,y=None,z=None,e=None,**kwargs):
		"""
		_update_current_position algorithm
		0. Instantiate default local variables necessary for function
		1. Gather axial move inputs from user into dict dims
		2. Calculate the number of steps to reach new location
		3. 
		"""
		# 0. Instantiate default local variables necessary for function
		xyzdistance = 0.0 	# distance of move
		edistance = 0.0 	# distance of extrusion
		move_time = 0.0 	# elapsed time during move
		# load output digits
		d = self.output_digits
		# 1. Gather axial input values from user input
		dims = {}
		if x is not None:
			dims[AXES[0]] = x
		if y is not None:
			dims[AXES[1]] = y
		if z is not None:
			dims[AXES[2]] = z
		if e is not None:
			dims[AXES[3]] = e

		for axes in dims.keys():
			# the user's desired coordinate destination is calculated (in mm)
			destination = dims[axes] + self._get_position(axes,'mm') if self.is_relative else dims[axes]
			# the destination's coordinates are converted to motor steps
			# the target position is rounded to the nearest step
			target = int(round(destination*self.mm_to_steps[axes]))
			# the difference in steps from current position to desired position is calculated
			diff = target - self._get_position(axes)
			# handle summing travel and extrusion distances
			if axes in MOTION_AXES:
				xyzdistance += (diff*self.steps_to_mm[axes])**2
			elif axes in EXTRUSION_AXES:
				edistance = abs(diff*self.steps_to_mm[axes])
				if target > self.max_e_position:
					ediff = target - self.max_e_position
					extruded_volume = ediff*self.steps_to_mm[axes]*self.syringe_cross_section # uL
					self.extrusion_volume += extruded_volume
					self.max_e_position = target
			self._current_position[axes] += diff
	
		# calculate Euclidean distance
		xyzdistance = math.sqrt(xyzdistance) # mm

		# calculate move time 
		if xyzdistance != 0.0:
			move_time = 60.*xyzdistance/self.speed
			if edistance != 0.0:
				espeed = 60.*edistance/move_time # mm/min
				flowrate = espeed*self.syringe_cross_section/60. # uL/s
				filamentarea = extruded_volume / xyzdistance # mm^2
				filamentwidth = 4*filamentarea / math.pi / self.layer_height # mm (assumes ellipse)
				print(";Extr. rate: {0:.{digits}f} mm/min ({1:.{digits}f} uL/s | {2:.{digits}f} mL/min)".format(espeed,flowrate,60.*flowrate/1000.,digits=d))
				print(";Extr. volume: {0:.{digits}f} uL| Filament area: {1:.{digits}f} mm^2".format(extruded_volume,filamentarea,digits=d))
				print(";Filament width (elliptical assumption): {0:.{digits}f} mm".format(filamentwidth,digits=d))
		elif xyzdistance == 0.0 and edistance != 0.0:
			move_time = 60.*edistance/self.speed
			espeed = 60.*edistance/move_time # mm/min
			flowrate = espeed*self.syringe_cross_section/60. # uL/s
			print(";Extr. rate: {0:.{digits}f} mm/min ({1:.{digits}f} uL/s | {2:.{digits}f} mL/min)".format(espeed,flowrate,60.*flowrate/1000.,digits=d))
			print(";Extr. volume {0:.{digits}f} uL".format(extruded_volume,digits=d))
			
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
				e = e/self.syringe_cross_section # mm
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
				e = e/self.syringe_cross_section # mm
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
				extruded_volume = ediff*self.steps_to_mm[axes]*self.syringe_cross_section # uL
				self.extrusion_volume += extruded_volume
				self.max_e_position = target
			self._current_position[axes] += diff

		# Add XYX displacement to total distance
		xydistance = 2*math.pi*radius # should be updated later to account for discrete movement
		self.travel_distance += xydistance
		move_time = 60.*xydistance/self.speed
		if edistance != 0.0:
			espeed = 60.*edistance/move_time # mm/min
			flowrate = espeed*self.syringe_cross_section/60. # uL/s
			d = self.output_digits
			print(";Extrusion rate: {0:.{digits}f} mm/min | Flow rate: {1:.{digits}f} uL/s".format(espeed,flowrate,digits=d))
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

	def set_feedrate(self,rate,extrusionunit='mm/min'):
		""" Set the feed rate (tool head speed) in mm/min
		Parameters
		----------
		rate : float
			The speed to move the tool head in mm/min
		extrusionunit : str
			Units to use when specifying extrusion rate ('mm/min', 'uL/min', mL/min or uL/s)
		"""
		d = self.output_digits
		if extrusionunit == 'mm/min':
			self.speed = rate
		elif extrusionunit == 'uL/min':
			self.speed = rate / self.syringe_cross_section
		elif extrusionunit == 'mL/min':
			self.speed = 1000*rate / self.syringe_cross_section
		elif extrusionunit == 'uL/s':
			self.speed = rate / (60.*self.syringe_cross_section)

		self.write(";Extr. rate: {0:.{digits}f} mm/min ({1:.{digits}f} uL/s | {2:.{digits}f} mL/min)".format(self.speed,self.speed*self.syringe_cross_section/60,self.speed*self.syringe_cross_section/1000,digits=d))
		self.write('G1 F{:.{digits}f}'.format(self.speed,digits=d))
		

	def relative(self):
		self.write('G91')
		self.is_relative = True

	def absolute(self):
		self.write('G90')
		self.is_relative = False

	def cold_extrusion(self,mode=True):
		msg = 'M302 P'
		if mode == True:
			msg += '1'
		else:
			msg += '0'
		self.allow_cold_extrusion = mode
		self.write(msg)

	def set_axis_steps_per_mm(self,x=None,y=None,z=None,e=None,comment=None):
		if x is not None:
			self.steps_to_mm[AXES[0]] = 1./x
			self.mm_to_steps[AXES[0]] = x
		if y is not None:
			self.steps_to_mm[AXES[1]] = 1./y
			self.mm_to_steps[AXES[1]] = y
		if z is not None:
			self.steps_to_mm[AXES[2]] = 1./z
			self.mm_to_steps[AXES[2]] = z
		if e is not None:
			self.steps_to_mm[AXES[3]] = 1./e
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
		self.print_blank_line()
		# set as relative move
		self.relative()
		# set the axis steps per unit
		self.set_axis_steps_per_mm(x=DEFAULT_AXIS_STEPS_PER_MM[0],y=DEFAULT_AXIS_STEPS_PER_MM[1],z=DEFAULT_AXIS_STEPS_PER_MM[2],e=DEFAULT_AXIS_STEPS_PER_MM[3])
		# turn off cold extrusion prevention
		self.cold_extrusion()
		# set initial speed
		self.set_feedrate(self.speed)
		self.print_blank_line()


	def header(self):
		# load the set output digits
		d = self.output_digits
		self.write(';Printer is using {}X microstepping'.format(self.microstepping))
		self.write(';There are {} steps per revolution of the motor.'.format(STEPS_PER_REVOLUTION))
		args = [axes+str(1000.*self.steps_to_mm[axes]) for axes in AXES]
		args = ' '.join(args)
		self.write(';Min. travel/extrusion distance (um): '+args)
		self.write(';Syringe type: {}'.format(self.syringe))
		self.write(';Syringe extrusion (uL/mm): {:.{digits}f}'.format(self.syringe_cross_section,digits=d))
		self.write(';Syringe waste volume (mL): {}'.format(SYRINGE_WASTE_SPACE[self.syringe]))
		self.write(';Min. extrudable volume (uL): {:.{digits}f}'.format(self.steps_to_mm[AXES[3]]*self.syringe_cross_section,digits=d))
		self.write(';Tip type: {}'.format(self.tip))
		self.write(';Tip diameter (mm): {:.{digits}f}'.format(self.tip_cross_section,digits=d))
		self.write(';Tip void volume (mL): {:.{digits}f}'.format(TIP_VOID_VOLUME[self.tip],digits=d))
		self.write(';Volumetric flow: {:.{digits}f} uL/min for every 100 mm/min'.format(100*self.syringe_cross_section,digits=d))
		self.write(';For syringe extrusion rate of 100 mm/min, tip extrusion rate is {:.{digits}f} mm/min'.format(100.0*self.syringe_cross_section/self.tip_cross_section,digits=d))

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
	def print_disc(self,r2,r1,step,thickness,direction='outwards'):
		num_ring = int(1+(r2-r1)/step)
		step_list = [step*i for i in range(num_ring)]
		radii = [r2-i for i in step_list]
		circums = [2*math.pi*r for r in radii]
		total_path_length = sum(circums)
		weights = [i/total_path_length for i in circums] # in mm
		# now calculate total volume
		vol = math.pi*thickness*((r2**2) - (r1**2))
		# calculate e move
		total_e = vol/self.syringe_cross_section
		e_list = [total_e*i for i in weights]
		# plan for move
		for i in range(num_ring):
			self.circular_move(radii[i],e=e_list[i])
			if i != (num_ring-1):
				self.move(x=step)

	def print_square(self,side,layerheight,spacing=0.2,redundancy=2,lift=0.0):
		self.print_blank_line()
		layervolume = layerheight*(side**2)
		msg1 = ";Printing square layer: {0} X {0} X {1}mm".format(side,layerheight)
		print(msg1)
		msg2 = ";Layer volume: {} uL".format(layervolume)
		print(msg2)
		if lift>0.0:
			self.move(z=-lift)
			self.move(x=-side/2.,y=-side/2.)
			self.move(z=lift)
		else:
			self.move(x=-side/2.,y=-side/2.)
		# 


# ========== Vessel functions ========== #
	def print_vessel(self,length,thickness):
		pass

# ========== Debug functions ========== # 
	def run_test(self):
		self.move(e=5)
		self.move(x=5,y=5,e=1.01,extrusionunit='uL')
		self.print_square(50.1,0.222)

		
if __name__ == "__main__":
	g = G(syringe='BD-1ml')
	g.run_test()
	g.summary_report()

	
