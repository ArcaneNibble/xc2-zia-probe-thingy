module top(
    (* LOC = "FB1_14" *)
    input but0,
    (* LOC = "FB1_15" *)
    input but1,
    (* LOC = "FB1_9" *)
    (* TERM = "TRUE" *)
    output led0,
    (* LOC = "FB1_10" *)
    (* TERM = "TRUE" *)
    output led1,
    (* LOC = "FB1_11" *)
    (* TERM = "TRUE" *)
    output led2
);

assign led0 = !but0 & !but1;
assign led1 = !but0 | !but1;
assign led2 = !but0 ^ !but1;

endmodule
