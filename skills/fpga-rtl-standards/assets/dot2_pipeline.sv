// Function: signed a*b + c*d, retaining full precision (2*P_DATA_W+1 bits).
// Clock/reset: i_clk rising edge; synchronous active-high i_rst.
// Interface: all four operands are one bundle qualified by i_data_dvalid.
// Timing: bundle sampled at E0 -> products at E1 -> output at E2.
// Throughput: one bundle per clock, no backpressure; invalid output data holds.
// Format: signed integers. For fixed point, raw result has twice the input
// fractional bits; no rounding, saturation, or scale change occurs here.
// Parameter contract: P_DATA_W >= 1.
module dot2_pipeline #(
    parameter integer P_DATA_W = 16
) (
    input  wire                              i_clk,
    input  wire                              i_rst,
    input  wire signed [P_DATA_W-1:0]         i_a_data,
    input  wire signed [P_DATA_W-1:0]         i_b_data,
    input  wire signed [P_DATA_W-1:0]         i_c_data,
    input  wire signed [P_DATA_W-1:0]         i_d_data,
    input  wire                              i_data_dvalid,
    output wire signed [2*P_DATA_W:0]         o_result_data,
    output wire                              o_result_dvalid
);
    localparam integer P_PRODUCT_W = 2 * P_DATA_W;

    logic signed [P_DATA_W-1:0]    ri_a_data;
    logic signed [P_DATA_W-1:0]    ri_b_data;
    logic signed [P_DATA_W-1:0]    ri_c_data;
    logic signed [P_DATA_W-1:0]    ri_d_data;
    logic                        ri_data_dvalid;

    logic signed [P_PRODUCT_W:0]  ro_result_data;
    logic                        ro_result_dvalid;
    assign o_result_data   = ro_result_data;
    assign o_result_dvalid = ro_result_dvalid;

    logic signed [P_PRODUCT_W-1:0] r_product_ab;
    logic signed [P_PRODUCT_W-1:0] r_product_cd;
    logic                          r_product_dvalid;
    wire signed [P_PRODUCT_W:0]    w_product_ab_ext;
    wire signed [P_PRODUCT_W:0]    w_product_cd_ext;

    // Sign-extend each product before the addition to retain the extra bit.
    assign w_product_ab_ext = {r_product_ab[P_PRODUCT_W-1], r_product_ab};
    assign w_product_cd_ext = {r_product_cd[P_PRODUCT_W-1], r_product_cd};

    always_ff @(posedge i_clk) begin
        if (i_rst) begin
            ri_a_data      <= '0;
            ri_b_data      <= '0;
            ri_c_data      <= '0;
            ri_d_data      <= '0;
            ri_data_dvalid <= 1'b0;
        end else begin
            ri_data_dvalid <= i_data_dvalid;
            if (i_data_dvalid) begin
                ri_a_data <= i_a_data;
                ri_b_data <= i_b_data;
                ri_c_data <= i_c_data;
                ri_d_data <= i_d_data;
            end
        end
    end

    always_ff @(posedge i_clk) begin
        if (i_rst) begin
            r_product_ab     <= '0;
            r_product_cd     <= '0;
            r_product_dvalid <= 1'b0;
        end else begin
            r_product_dvalid <= ri_data_dvalid;
            if (ri_data_dvalid) begin
                r_product_ab <= ri_a_data * ri_b_data;
                r_product_cd <= ri_c_data * ri_d_data;
            end
        end
    end

    always_ff @(posedge i_clk) begin
        if (i_rst) begin
            ro_result_data   <= '0;
            ro_result_dvalid <= 1'b0;
        end else begin
            ro_result_dvalid <= r_product_dvalid;
            if (r_product_dvalid)
                ro_result_data <= w_product_ab_ext + w_product_cd_ext;
        end
    end
endmodule
