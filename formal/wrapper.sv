module rvfi_wrapper (
	input         clock,
	input         reset,
	`RVFI_OUTPUTS
);
	(* keep *) `rvformal_rand_reg [31:0] ibus_dat_r_randval;
	(* keep *) `rvformal_rand_reg ibus_ack_randval;

        assign ibus_dat_r = ibus_dat_r_randval;
        assign ibus_ack = ibus_ack_randval;

	(* keep *) wire [29:0] ibus_adr;
	(* keep *) wire [31:0] ibus_dat_w;
	(* keep *) wire [31:0] ibus_dat_r;
	(* keep *) wire [ 3:0] ibus_sel;
	(* keep *) wire        ibus_cyc;
	(* keep *) wire        ibus_stb;
	(* keep *) wire        ibus_ack;
	(* keep *) wire        ibus_we;
	(* keep *) wire [ 2:0] ibus_cti;
	(* keep *) wire [ 1:0] ibus_bte;
	(* keep *) wire        ibus_err;

	rv32_cpu uut (
		.clk       (clock),
		.rst       (reset),

                .ibus__adr          (ibus_adr),
		.ibus__dat_w        (ibus_dat_w),
		.ibus__dat_r        (ibus_dat_r),
		.ibus__sel          (ibus_sel),
		.ibus__cyc          (ibus_cyc),
		.ibus__stb          (ibus_stb),
		.ibus__ack          (ibus_ack),
		.ibus__we           (ibus_we),
		.ibus__cti          (ibus_cti),
		.ibus__bte          (ibus_bte),
		.ibus__err          (ibus_err),

		.rvfi__valid        (rvfi_valid),
		.rvfi__order        (rvfi_order),
		.rvfi__insn         (rvfi_insn),
		.rvfi__trap         (rvfi_trap),
		.rvfi__halt         (rvfi_halt),
		.rvfi__intr         (rvfi_intr),
		.rvfi__mode         (rvfi_mode),
		.rvfi__ixl          (rvfi_ixl),
		.rvfi__rs1_addr     (rvfi_rs1_addr),
		.rvfi__rs2_addr     (rvfi_rs2_addr),
		.rvfi__rs1_rdata    (rvfi_rs1_rdata),
		.rvfi__rs2_rdata    (rvfi_rs2_rdata),
		.rvfi__rd_addr      (rvfi_rd_addr),
		.rvfi__rd_wdata     (rvfi_rd_wdata),
		.rvfi__pc_rdata     (rvfi_pc_rdata),
		.rvfi__pc_wdata     (rvfi_pc_wdata),
		.rvfi__mem_addr     (rvfi_mem_addr),
		.rvfi__mem_rmask    (rvfi_mem_rmask),
		.rvfi__mem_wmask    (rvfi_mem_wmask),
		.rvfi__mem_rdata    (rvfi_mem_rdata),
		.rvfi__mem_wdata    (rvfi_mem_wdata),
	);

endmodule
