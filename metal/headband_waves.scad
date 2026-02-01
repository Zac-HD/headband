// Crown for laser cutting - 2D design
// Half crown, will be mirrored

// Parameters
half_width = 300;        // Half of 60cm
band_height = 25;        // Base height
top_amplitude = 10;      // Top sine wave amplitude
bottom_amplitude = 5;    // Bottom sine wave amplitude
wave_thickness = 5;      // Thickness of each wave band
connector_thickness = 2; // Thickness of connecting wave
connector_period = 30;   // Period of connecting wave
end_cap_width = 5;       // Width of end cap

// Gem holder parameters
gem_width = 25;          // Gem width (horizontal)
gem_height = 15;         // Gem height (vertical)
gem_holder_margin = 3;   // Extra material around gem

// Electronics holder parameters
holder_width = 40;
holder_panel_height = 30;
holder_base_depth = 10;
holder_outline = 3;
holder_corner_radius = 5;
holder_num_peaks = 4;      // Upper peaks (one at each edge, rest free)
holder_wave_thickness = 2;

// Resolution
steps = 200;
cap_steps = 30;

// Top edge: 3/4 sine wave starting at neutral (0, 25)
function top_y(x) = band_height + top_amplitude * sin(x / half_width * 270);

// Bottom edge: full sine wave, starting at minimum (0, 0)
function bottom_y(x) = bottom_amplitude + bottom_amplitude * -cos(x / half_width * 360);

// Inner edges
function top_inner(x) = top_y(x) - wave_thickness;
function bottom_inner(x) = bottom_y(x) + wave_thickness;

// Connector wave: oscillates between inner edges
function connector_mid(x) =
    let(mid = (top_inner(x) + bottom_inner(x)) / 2,
        amp = (top_inner(x) - bottom_inner(x)) / 2 + connector_thickness/2)
    mid + amp * sin(x / connector_period * 360);

// Top wave band
module top_wave() {
    top_outer = [for (i = [0 : steps])
        let(x = i * half_width / steps)
        [x, top_y(x)]
    ];

    top_inner_pts = [for (i = [steps : -1 : 0])
        let(x = i * half_width / steps)
        [x, top_inner(x)]
    ];

    polygon(concat(top_outer, top_inner_pts));
}

// Bottom wave band
module bottom_wave() {
    bottom_outer = [for (i = [0 : steps])
        let(x = i * half_width / steps)
        [x, bottom_inner(x)]
    ];

    bottom_inner_pts = [for (i = [steps : -1 : 0])
        let(x = i * half_width / steps)
        [x, bottom_y(x)]
    ];

    polygon(concat(bottom_outer, bottom_inner_pts));
}

// Connecting wave - 2mm thick perpendicular to curve
module connector_wave() {
    connector_extend = half_width + 3;

    function wave_y(x) = connector_mid(min(x, half_width));

    function wave_dy(x) =
        let(dx = 0.1)
        (wave_y(x + dx) - wave_y(x - dx)) / (2 * dx);

    function offset_point(x, dist) =
        let(dy = wave_dy(x),
            len = sqrt(1 + dy * dy),
            nx = -dy / len,
            ny = 1 / len)
        [x + nx * dist, wave_y(x) + ny * dist];

    // Continue the sine wave pattern beyond half_width
    function wave_y_extended(x) =
        let(mid = (top_inner(half_width) + bottom_inner(half_width)) / 2,
            amp = (top_inner(half_width) - bottom_inner(half_width)) / 2 + connector_thickness/2)
        mid + amp * sin(x / connector_period * 360);

    function wave_dy_extended(x) =
        let(dx = 0.1)
        (wave_y_extended(x + dx) - wave_y_extended(x - dx)) / (2 * dx);

    function offset_point_extended(x, dist) =
        let(dy = wave_dy_extended(x),
            len = sqrt(1 + dy * dy),
            nx = -dy / len,
            ny = 1 / len)
        [x + nx * dist, wave_y_extended(x) + ny * dist];

    // Main wave up to half_width
    main_steps = floor(steps * half_width / connector_extend);
    extend_steps = steps - main_steps;

    outer_pts_main = [for (i = [0 : main_steps])
        let(x = i * half_width / main_steps)
        offset_point(x, connector_thickness/2)
    ];

    outer_pts_ext = [for (i = [1 : extend_steps])
        let(x = half_width + i * (connector_extend - half_width) / extend_steps)
        offset_point_extended(x, connector_thickness/2)
    ];

    inner_pts_ext = [for (i = [extend_steps : -1 : 1])
        let(x = half_width + i * (connector_extend - half_width) / extend_steps)
        offset_point_extended(x, -connector_thickness/2)
    ];

    inner_pts_main = [for (i = [main_steps : -1 : 0])
        let(x = i * half_width / main_steps)
        offset_point(x, -connector_thickness/2)
    ];

    polygon(concat(outer_pts_main, outer_pts_ext, inner_pts_ext, inner_pts_main));
}

// End cap - half circle
module end_cap() {
    top_at_end = top_y(half_width);
    bottom_at_end = bottom_y(half_width);

    mid_y = (top_at_end + bottom_at_end) / 2;
    radius = (top_at_end - bottom_at_end) / 2;
    inner_radius = radius - end_cap_width;

    outer_arc = [for (i = [0 : cap_steps])
        let(angle = -90 + i * 180 / cap_steps)
        [half_width + radius * cos(angle), mid_y + radius * sin(angle)]
    ];

    inner_arc = [for (i = [cap_steps : -1 : 0])
        let(angle = -90 + i * 180 / cap_steps)
        [half_width + inner_radius * cos(angle), mid_y + inner_radius * sin(angle)]
    ];

    polygon(concat(outer_arc, inner_arc));
}

// Gem holder - solid oval in center
module gem_holder() {
    top_at_center = top_y(0);
    bottom_at_center = bottom_y(0);
    center_y = (top_at_center + bottom_at_center) / 2;

    outer_ry = (top_at_center - bottom_at_center) / 2;
    outer_rx = outer_ry * 0.6;

    translate([0, center_y])
        scale([outer_rx, outer_ry])
            circle(r = 1, $fn = 60);
}

// Electronics holder - foldable panel with sine wave fill
module electronics_holder() {
    // Position
    holder_right = half_width - end_cap_width;
    holder_left = holder_right - holder_width;

    // Panel bounds
    panel_top = -holder_base_depth;
    panel_bottom = panel_top - holder_panel_height;

    // Wave spans inner panel width (peaks meet inner edges of side walls)
    t = holder_wave_thickness / 2;
    wave_left = holder_left + holder_outline;
    wave_right = holder_right - holder_outline;
    wave_width = wave_right - wave_left;

    // Sine wave: N peaks means N-1 periods
    wave_period = wave_width / (holder_num_peaks - 1);
    k = 360 / wave_period;  // angular frequency in degrees per unit

    // Position wave so:
    // - outer/top edge at peaks touches panel_top
    // - inner/top edge at troughs touches inner edge of bottom outline
    inner_top = panel_top;
    inner_bottom = panel_bottom + holder_outline;
    // wave_mid + wave_amp + t = inner_top  →  wave_mid + wave_amp = inner_top - t
    // wave_mid - wave_amp + t = inner_bottom  →  wave_mid - wave_amp = inner_bottom - t
    // Adding: 2*wave_mid = inner_top + inner_bottom - 2t
    // Subtracting: 2*wave_amp = inner_top - inner_bottom
    wave_mid = (inner_top + inner_bottom) / 2 - t;
    wave_amp = (inner_top - inner_bottom) / 2;

    // Wave center line
    function wave_y(x) = wave_mid + wave_amp * cos((x - wave_left) * k);

    // Derivative (for normal calculation)
    function wave_dy(x) = -wave_amp * k * PI/180 * sin((x - wave_left) * k);

    // Vertical connectors from bottom wave to panel
    bottom_at_right = bottom_y(holder_right);
    bottom_at_left = bottom_y(holder_left);

    // Left vertical
    translate([holder_left, panel_top])
        square([holder_outline, bottom_at_left - panel_top]);

    // Right vertical
    translate([holder_right - holder_outline, panel_top])
        square([holder_outline, bottom_at_right - panel_top]);

    // Panel outline (left, bottom, right edges with rounded corners)
    // Left edge
    translate([holder_left, panel_bottom + holder_corner_radius])
        square([holder_outline, holder_panel_height - holder_corner_radius]);

    // Right edge
    translate([holder_right - holder_outline, panel_bottom + holder_corner_radius])
        square([holder_outline, holder_panel_height - holder_corner_radius]);

    // Bottom edge
    translate([holder_left + holder_corner_radius, panel_bottom])
        square([holder_width - 2*holder_corner_radius, holder_outline]);

    // Bottom-left corner (90 degree arc)
    translate([holder_left + holder_corner_radius, panel_bottom + holder_corner_radius])
        difference() {
            circle(r = holder_corner_radius, $fn = 30);
            circle(r = holder_corner_radius - holder_outline, $fn = 30);
            translate([-holder_corner_radius, 0]) square([2*holder_corner_radius, holder_corner_radius]);
            translate([0, -holder_corner_radius]) square([holder_corner_radius, 2*holder_corner_radius]);
        }

    // Bottom-right corner (90 degree arc)
    translate([holder_right - holder_corner_radius, panel_bottom + holder_corner_radius])
        difference() {
            circle(r = holder_corner_radius, $fn = 30);
            circle(r = holder_corner_radius - holder_outline, $fn = 30);
            translate([-holder_corner_radius, 0]) square([2*holder_corner_radius, holder_corner_radius]);
            translate([-holder_corner_radius, -holder_corner_radius]) square([holder_corner_radius, 2*holder_corner_radius]);
        }

    // Sine wave as union of overlapping circles along path
    wave_steps = 400;
    for (i = [0:wave_steps]) {
        x = wave_left + i * wave_width / wave_steps;
        translate([x, wave_y(x)]) circle(r = t, $fn = 64);
    }
}

// Render half crown and mirror
module half_crown() {
    top_wave();
    bottom_wave();
    connector_wave();
    end_cap();
    electronics_holder();
}

half_crown();
mirror([1, 0, 0]) half_crown();
gem_holder();
