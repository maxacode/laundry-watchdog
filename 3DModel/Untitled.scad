/* 
   Smart Washer Sensor Enclosure
   Raspberry Pi Pico W + MPU-6050
*/

$fn = 64; // High resolution for smooth cylinders

// ==========================================
// CONFIGURATION VARIABLES
// ==========================================

// Printer Tolerances
clearance = 0.4;    // Adds wiggle room for sliding lid
wall = 2.0;         // Wall thickness
bottom_thick = 2.0; // Floor thickness

// Magnet Dimensions (2x 10mm x 1.75mm)
mag_dia = 10.4;     // Slightly oversized for easy gluing
mag_depth = 1.85;   // Flush recess depth

// Pico W Dimensions (Standard)
pico_l = 51.0;
pico_w = 21.0;
pico_hole_pitch_l = 47.0; // Distance between holes length-wise
pico_hole_pitch_w = 17.0; // Distance between holes width-wise
pico_peg_dia = 1.8;       // Fit inside 2.1mm Pico holes

// Sensor Dimensions (34x16x10mm)
sens_l = 34.0;
sens_w = 16.0;
sens_peg_dia = 2.6;       // Fit inside 3.0mm holes
// IMPORTANT: Measure the distance between the two holes on your exact module
sens_hole_pitch = 10.0;   // <--- CHANGE THIS based on your sensor
sens_hole_x_offset = 31.0; // Distance from front edge to the holes

// Internal Case Dimensions
int_l = pico_l + 4;               // 55mm internal length
int_w = pico_w + sens_w + 10;     // 47mm internal width (5mm gap + margins)
int_h = 22.0;                     // Generous height for wiring and 10mm sensor

// ==========================================
// GENERATION MODULES
// ==========================================

// Move lid to the side for printing
translate([0, int_w + 15, 0]) 
    case_lid();

case_body();

module case_body() {
    difference() {
        // 1. Main solid block
        cube([int_l + wall*2, int_w + wall*2, int_h + bottom_thick]);
        
        // 2. Hollow out the inside
        translate([wall, wall, bottom_thick])
            cube([int_l, int_w, int_h + 1]);
            
        // 3. Sliding lid rail grooves (Left and Right walls)
        translate([wall, wall/2, int_h + bottom_thick - 2])
            cube([int_l + wall + 1, int_w + wall, 2.5]); 
            
        // 4. Open the back wall completely for the lid to enter
        translate([int_l + wall, wall/2, int_h + bottom_thick - 2])
            cube([wall + 1, int_w + wall, 5]); 
            
        // 5. Pico USB Cutout 
        // Centered on the Pico's Y position
        translate([-1, wall + (pico_w/2) - 4.5, bottom_thick + 2.5])
            cube([wall + 2, 9.0, 7.0]);
            
        // 6. Magnet Recesses on the underside
        // Front Magnet
        translate([12, (int_w + wall*2)/2, -0.01])
            cylinder(d=mag_dia, h=mag_depth);
        // Back Magnet
        translate([(int_l + wall*2) - 12, (int_w + wall*2)/2, -0.01])
            cylinder(d=mag_dia, h=mag_depth);
    }
    
    // Add Pico W Mounting Pegs
    translate([wall + 2, wall, bottom_thick]) {
        pico_pegs();
    }
    
    // Add Sensor Mounting Pegs
    // Placed next to the Pico with a 5mm gap
    translate([wall + 2, wall + pico_w + 5, bottom_thick]) {
        sensor_pegs();
    }
}

module pico_pegs() {
    // Pico holes are inset 2mm from the edges
    x_inset = (pico_l - pico_hole_pitch_l) / 2;
    y_inset = (pico_w - pico_hole_pitch_w) / 2;
    
    peg_positions = [
        [x_inset, y_inset],
        [x_inset + pico_hole_pitch_l, y_inset],
        [x_inset, y_inset + pico_hole_pitch_w],
        [x_inset + pico_hole_pitch_l, y_inset + pico_hole_pitch_w]
    ];
    
    for (pos = peg_positions) {
        translate([pos[0], pos[1], 0]) {
            // Base standoff to lift PCB
            cylinder(d=5.0, h=2.5);
            // Alignment nub to slide through PCB hole
            cylinder(d=pico_peg_dia, h=4.5);
        }
    }
}

module sensor_pegs() {
    // Two holes located on one side
    y_center = sens_w / 2;
    
    peg_positions = [
        [sens_hole_x_offset, y_center - (sens_hole_pitch/2)],
        [sens_hole_x_offset, y_center + (sens_hole_pitch/2)]
    ];
    
    for (pos = peg_positions) {
        translate([pos[0], pos[1], 0]) {
            // Base standoff
            cylinder(d=5.5, h=2.5);
            // Alignment nub
            cylinder(d=sens_peg_dia, h=4.5);
        }
    }
    
    // Add a blank support standoff at the other end so the board doesn't tilt
    translate([2, y_center, 0])
        cylinder(d=5.5, h=2.5);
}

module case_lid() {
    // Lid is slightly narrower and shorter than the grooves to slide easily
    lid_l = int_l + wall - clearance;
    lid_w = int_w + wall - clearance*2;
    lid_h = 2.0; // 2mm thick lid
    
    cube([lid_l, lid_w, lid_h]);
    
    // Add a small pull tab to the back edge for easy removal
    translate([lid_l - 4, lid_w/2 - 5, lid_h])
        cube([4, 10, 2]);
}