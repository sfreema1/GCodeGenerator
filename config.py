import math
# Configuration file
# Set some basic print characteristics up here
MOTION_AXES = ['X','Y','Z']
EXTRUSION_AXES = ['E']
# All axes
AXES = tuple(MOTION_AXES + EXTRUSION_AXES)
# number of steps per mm for X,Y,Z,E axes
DEFAULT_AXIS_STEPS_PER_MM = (80.0,80.0,400.0,3540)
MOTOR_STEP_ANGLE = 1.8 # in degree
MICROSTEPPING = 16
STEPS_PER_REVOLUTION = int(MICROSTEPPING*360/MOTOR_STEP_ANGLE)

# Choose tip type
TIP = "JG24-1.25TTX"

# Choose well plate 
WELL_PLATE = "48-well plate"

# Calculated statistics
# Minimum travel distance for each axes
MM_PER_STEP = tuple([1./axes for axes in DEFAULT_AXIS_STEPS_PER_MM])

# Syringe and tip database (dictionaries)
SYRINGE_DIAMETER = {"BD-1ml":4.78,"BD-3ml":8.66,"BD-5ml":12.06,"BD-10ml":14.5} # mm
SYRINGE_WASTE_SPACE = {"BD-1ml":0.07,"BD-3ml":0.07,"BD-5ml":0.075,"BD-10ml":0.10} # ml
TIP_ID = {"JG24-1.25TTX":0.330,"JG22-1.25TTX":0.430} # mm
"""To calculate the void volume of a tip
# 1. Weigh out 1 ml of water (record density)
# 2. Weigh out the tip
# 3. Fill the syringe with tip with the 1 ml of water (record)
# 4. Remove the tip with the water in the tip and weigh the remaining syringe with liquid in it (record)
# 5. Calculate the difference and subtract the weight of the tip
# 6. Divide by the density of the water to calculate the volume in the tip
"""
TIP_VOID_VOLUME = {"JG24-1.25TTX":0.15,"JG22-1.25TTX":0.13} # ml

# Well plate dimensions


# Tip calculated dimensions
TIP_CROSS_SECTIONAL_DIAMETER = TIP_ID[TIP] # mm
TIP_CROSS_SECTIONAL_AREA = math.pi*(TIP_CROSS_SECTIONAL_DIAMETER/2)**2 # uL/mm

# Environmental parameters
SAP = 14.692 # psi

# Vessel printing
PIPET = "VWR-1ml"
PIPET_OD = {"VWR-1ml":4.9} # mm

