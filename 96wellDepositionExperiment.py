from main import *

# Input parameters for experiment
well_volume = 25 # microliters
ctc = 9.1 # mm
z_lift = 15 # mm
num_rows = 0
num_columns = 0
travel_rate = 1000
extrusion_rate = 300
retraction_rate = 100
num_replicates = 3

# Create the G object
g = G(output_digits=4,initial_feedrate=100)

for i in range(num_replicates):
	g.set_feedrate(1,extrusionunit='mL/min')
	g.move(e=well_volume,extrusionunit='uL')
	g.set_feedrate(travel_rate)
	g.move(z=-z_lift)
	g.move(x=-ctc)
	g.move(z=z_lift)
	num_columns += 1
	g.print_blank_line()

for i in range(num_replicates):
	g.set_feedrate(5,extrusionunit='mL/min')
	g.move(e=well_volume,extrusionunit='uL')
	g.set_feedrate(travel_rate)
	g.move(z=-z_lift)
	g.move(x=-ctc)
	g.move(z=z_lift)
	num_columns += 1
	g.print_blank_line()

for i in range(num_replicates):
	g.set_feedrate(10,extrusionunit='mL/min')
	g.move(e=well_volume,extrusionunit='uL')
	g.set_feedrate(travel_rate)
	g.move(z=-z_lift)
	if i != (num_replicates-1):
		g.move(x=-ctc)
		g.move(z=z_lift)
		num_columns += 1
	g.print_blank_line()

num_rows += 1

g.set_feedrate(travel_rate)
g.move(y=-num_rows*ctc)
g.move(x=num_columns*ctc)

g.set_feedrate(retraction_rate)
g.move(e=-250,extrusionunit='uL')

g.summary_report()