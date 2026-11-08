/* 
   Smart Washer Sensor Enclosure - V2 (Low Profile)
   Raspberry Pi Pico W + MPU-6050
*/

$fn = 64; // High resolution for smooth cylinders

// ==========================================
// CONFIGURATION VARIABLES
// ==========================================

// Printer Tolerances
clearance = 0.2;    // Tightened for dovetail sliding lid
wall = 2.0;         // Wall thickness
bottom_thick = 2.0; // Floor thickness

// Magnet Dimensions (2x 10mm x 1.75mm)
mag_dia = 10.4;     
mag_depth = 1.85;   

// Pico W Dimensions (Standard)
pico_l = 51.0;
pico_w = 21.0;
pico_hole_pitch_l = 47.0; // Distance between holes length-wise
pico_hole_pitch_w = 17.0; // Distance between holes width-wise
pico_peg_dia = 1.9;       // Slightly smaller for easier fit into 2.1mm holes

// Sensor Dimensions (34x16x10mm)
sens_l = 34.0;
sens_w = 16.0;
sens_peg_dia = 2.7;       
sens_hole_pitch = 10.0;   // <--- Adjust based on your specific MPU-6050
sens_hole_x_offset = 31.0; 

// Internal Case Dimensions
int_l = 55.0;                     
int_w = pico_w + sens_w + 12.0;   // Expanded slightly to give boards breathing room
int_h = 9.0;                      // Reduced to ~40% of original height

// Board Positioning (Offsets from internal walls)
board_x = wall + 0.5; // 0.5mm from front wall so USB reaches the edge
board_y = wall + 3.0; // 3.0mm from left wall to clear the pins

sensor_x = wall + 10.0;
sensor_y = board_y + pico_w + 4.0; 

// ==========================================
// GENERATION MODULES
// ==========================================

// Move lid to the side for printing
translate([0, int_w + 20, 0]) 
    case_lid();

case_body();

module case_body() {
    difference() {
        // 1. Main solid block
        cube([int_l + wall*2, int_w + wall*2, int_h + bottom_thick]);
        
        // 2. Hollow out the inside
        translate([wall, wall, bottom_thick])
            cube([int_l, int_w, int_h + 1]);
            
        // 3. Dovetail Sliding Rail Grooves
        dovetail_groove_cut();
            
        // 4. Open the back wall completely for the lid to enter
        translate([int_l + wall - 1, wall/2, int_h + bottom_thick - 2.5])
            cube([wall + 2, int_w + wall, 5]); 
            
        // 5. Pico USB Cutout (Linked exactly to board placement)
        usb_y = board_y + (pico_w / 2);
        translate([-1, usb_y - 5.0, bottom_thick + 1.5])
            cube([wall + 2, 10.0, 7.0]);
            
        // 6. Magnet Recesses on the underside
        translate([12, (int_w + wall*2)/2, -0.01])
            cylinder(d=mag_dia, h=mag_depth);
        translate([(int_l + wall*2) - 12, (int_w + wall*2)/2, -0.01])
            cylinder(d=mag_dia, h=mag_depth);
    }
    
    // Add Pico W Mounting Pegs
    translate([board_x, board_y, bottom_thick]) {
        pico_pegs();
    }
    
    // Add Sensor Mounting Pegs
    translate([sensor_x, sensor_y, bottom_thick]) {
        sensor_pegs();
    }
}

module dovetail_groove_cut() {
    // Cuts a trapezoidal groove into the side walls for the lid
    hull() {
        // Top opening (narrow)
        translate([-1, wall - 0.5, int_h + bottom_thick - 0.01])
            cube([int_l + wall + 2, int_w + 1.0, 0.1]);
        // Base of the dovetail (wide)
        translate([-1, wall/2, int_h + bottom_thick - 2.5])
            cube([int_l + wall + 2, int_w + wall, 0.1]);
    }
}

module pico_pegs() {
    // Exact hole coordinates relative to Pico's bottom-left corner
    peg_positions = [
        [2.0, 2.0],
        [2.0 + pico_hole_pitch_l, 2.0],
        [2.0, 2.0 + pico_hole_pitch_w],
        [2.0 + pico_hole_pitch_l, 2.0 + pico_hole_pitch_w]
    ];
    
    for (pos = peg_positions) {
        translate([pos[0], pos[1], 0]) {
            cylinder(d=5.0, h=2.5);          // Base standoff
            cylinder(d=pico_peg_dia, h=4.5); // Alignment nub
        }
    }
}

module sensor_pegs() {
    y_center = sens_w / 2;
    peg_positions = [
        [sens_hole_x_offset, y_center - (sens_hole_pitch/2)],
        [sens_hole_x_offset, y_center + (sens_hole_pitch/2)]
    ];
    
    for (pos = peg_positions) {
        translate([pos[0], pos[1], 0]) {
            cylinder(d=5.5, h=2.5);
            cylinder(d=sens_peg_dia, h=4.5);
        }
    }
    // Blank support standoff at the other end
    translate([3.0, y_center, 0])
        cylinder(d=5.5, h=2.5);
}

module case_lid() {
    lid_l = int_l + wall - 1.0; 
    
    // The lid prints flat (upside down relative to how it slides in)
    // The wide bottom provides a clean first layer on the build plate.
    hull() {
        // Wide part (prints against the bed)
        translate([0, wall/2 + clearance, 0])
            cube([lid_l, int_w + wall - 2*clearance, 0.1]);
        // Narrow part (top of the print)
        translate([0, wall - 0.5 + clearance, 2.5 - clearance])
            cube([lid_l, int_w + 1.0 - 2*clearance, 0.1]);
    }
    
    // Pull tab for easy removal
    translate([lid_l - 4.0, wall + int_w/2 - 5.0, 2.5 - clearance])
        cube([4.0, 10.0, 2.0]);
}