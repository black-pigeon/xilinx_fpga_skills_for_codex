`timescale 1ns/1ps

// Testbench only: initial, delays and random stimulus are intentionally non-synthesizable.
module tb_dot2_pipeline;
    parameter integer P_DATA_W = 4;
    localparam integer P_RESULT_W = 2 * P_DATA_W + 1;
    localparam integer P_MIN = -(2 ** (P_DATA_W - 1));
    localparam integer P_MAX = (2 ** (P_DATA_W - 1)) - 1;

    logic i_clk = 1'b0;
    logic i_rst;
    logic signed [P_DATA_W-1:0] i_a_data, i_b_data, i_c_data, i_d_data;
    logic i_data_dvalid;
    wire signed [P_RESULT_W-1:0] o_result_data;
    wire o_result_dvalid;
    logic signed [P_RESULT_W-1:0] r_expected_data [0:2];
    logic r_expected_valid [0:2];
    integer r_checks = 0;
    integer r_outputs = 0;
    integer r_seed = 32'h1a2b3c4d;
    integer a, b, c, d, n;
    integer unsigned r_random_value;
    longint signed r_golden;

    dot2_pipeline #(.P_DATA_W(P_DATA_W)) dut (
        .i_clk(i_clk), .i_rst(i_rst),
        .i_a_data(i_a_data), .i_b_data(i_b_data),
        .i_c_data(i_c_data), .i_d_data(i_d_data),
        .i_data_dvalid(i_data_dvalid),
        .o_result_data(o_result_data), .o_result_dvalid(o_result_dvalid)
    );

    always #5 i_clk = ~i_clk;

    task automatic tick(
        input integer a_in, b_in, c_in, d_in,
        input logic valid_in, reset_in
    );
        @(negedge i_clk);
        i_a_data = P_DATA_W'(a_in);
        i_b_data = P_DATA_W'(b_in);
        i_c_data = P_DATA_W'(c_in);
        i_d_data = P_DATA_W'(d_in);
        i_data_dvalid = valid_in;
        i_rst = reset_in;
        r_golden = (longint'($signed(i_a_data)) * longint'($signed(i_b_data)))
                 + (longint'($signed(i_c_data)) * longint'($signed(i_d_data)));
        @(posedge i_clk);
        #1;
        if (reset_in) begin
            for (integer k = 0; k < 3; k = k + 1) begin
                r_expected_data[k] = '0;
                r_expected_valid[k] = 1'b0;
            end
        end else begin
            r_expected_data[2] = r_expected_data[1];
            r_expected_data[1] = r_expected_data[0];
            r_expected_data[0] = P_RESULT_W'(r_golden);
            r_expected_valid[2] = r_expected_valid[1];
            r_expected_valid[1] = r_expected_valid[0];
            r_expected_valid[0] = valid_in;
        end
        r_checks = r_checks + 1;
        if (o_result_dvalid !== r_expected_valid[2])
            $fatal(1, "valid mismatch width=%0d check=%0d", P_DATA_W, r_checks);
        if (o_result_dvalid) begin
            r_outputs = r_outputs + 1;
            if (o_result_data !== r_expected_data[2])
                $fatal(1, "data mismatch width=%0d got=%0d expected=%0d", P_DATA_W,
                       $signed(o_result_data), $signed(r_expected_data[2]));
        end
        if (reset_in && o_result_data !== '0)
            $fatal(1, "reset did not clear output data");
    endtask

    initial begin
        i_rst = 1'b1;
        i_data_dvalid = 1'b0;
        i_a_data = '0; i_b_data = '0; i_c_data = '0; i_d_data = '0;
        for (integer k = 0; k < 3; k = k + 1) begin
            r_expected_data[k] = '0;
            r_expected_valid[k] = 1'b0;
        end
        tick(0, 0, 0, 0, 0, 1);
        tick(P_MIN, P_MIN, P_MIN, P_MIN, 1, 0);
        tick(P_MIN, P_MAX, P_MIN, P_MAX, 1, 0);
        tick(P_MAX, P_MAX, P_MIN, P_MIN, 1, 0);
        tick(0, 0, 0, 0, 0, 0);
        tick(P_MIN, 1, P_MAX, -1, 1, 0);
        // Reset with valid data still in flight; no stale result may escape.
        tick(P_MAX, P_MAX, P_MAX, P_MAX, 1, 1);
        tick(0, 0, 0, 0, 0, 0);
        tick(0, 0, 0, 0, 0, 0);
        tick(0, 0, 0, 0, 0, 0);
        if (P_DATA_W <= 2) begin
            for (a = P_MIN; a <= P_MAX; a = a + 1)
                for (b = P_MIN; b <= P_MAX; b = b + 1)
                    for (c = P_MIN; c <= P_MAX; c = c + 1)
                        for (d = P_MIN; d <= P_MAX; d = d + 1)
                            tick(a, b, c, d, 1, 0);
        end
        for (n = 0; n < 400; n = n + 1) begin
            a = $random(r_seed); b = $random(r_seed);
            c = $random(r_seed); d = $random(r_seed);
            r_random_value = $unsigned($random(r_seed));
            tick(a, b, c, d, (n % 5 != 0), r_random_value % 31 == 0);
        end
        repeat (3) tick(0, 0, 0, 0, 0, 0);
        $display("PASS width=%0d checks=%0d valid_outputs=%0d", P_DATA_W, r_checks, r_outputs);
        $finish;
    end
endmodule
