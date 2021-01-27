//
// chargen.v
//
// Copyright 2020, Gary Wong <gtw@gnu.org>
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions
// are met:
// 
// 1. Redistributions of source code must retain the above copyright
//    notice, this list of conditions and the following disclaimer.
// 2. Redistributions in binary form must reproduce the above copyright
//    notice, this list of conditions and the following disclaimer in
//    the documentation and/or other materials provided with the
//    distribution.
// 
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
// FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
// COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
// (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
// HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
// STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
// OF THE POSSIBILITY OF SUCH DAMAGE.

module chargen( input clk, input linesync, input framesync,
		input[ 10:0 ] addr, input[ 31:0 ] wdata, output[ 31:0 ] data,
		input[ 3:0 ] we,
		output reg[ 10:0 ] sladdr, output reg[ 7:0 ] rdata,
		output reg[ 7:0 ] gdata, output reg[ 7:0 ] bdata,
		output reg slwe );

    // Screen memory
    reg[ 7:0 ] char0[ 0:2047 ];
    reg[ 7:0 ] attr0[ 0:2047 ];
    reg[ 7:0 ] char1[ 0:2047 ];
    reg[ 7:0 ] attr1[ 0:2047 ];
    initial $readmemh( "char0.hex", char0 );
    initial $readmemh( "attr0.hex", attr0 );
    initial $readmemh( "char1.hex", char1 );
    initial $readmemh( "attr1.hex", attr1 );

    // Read/write port
    reg[ 10:0 ] rwaddrl;
    always @( posedge clk ) begin
	if( we[ 0 ] )
            char0[ addr ] <= wdata[ 7:0 ];
	if( we[ 1 ] )
            attr0[ addr ] <= wdata[ 15:8 ];
	if( we[ 2 ] )
            char1[ addr ] <= wdata[ 23:16 ];
	if( we[ 3 ] )
            attr1[ addr ] <= wdata[ 31:24 ];
	rwaddrl <= addr;
    end
    assign data = { attr1[ rwaddrl ], char1[ rwaddrl ],
		    attr0[ rwaddrl ], char0[ rwaddrl ] };
    
    // Font memory
    reg[ 3:0 ] font[ 0:65535 ]; // 7 bits char, 5 bits y, 4 bits x
    initial $readmemh( "font.hex", font );   

    reg fs;
    reg ls;    
    reg oldls;
    always @( posedge clk ) begin
	fs <= framesync;
	ls <= linesync;
	oldls <= ls;
    end
    
    reg[ 11:0 ] x;
    always @( posedge clk )
	if( oldls && !ls )
	    x <= 0;
	else if( !x[ 11 ] )
	    x <= x + 1'b1;
	else
	    x <= x;

    reg[ 10:0 ] y;
    always @( posedge clk )
	if( fs )
	    y <= 0;
	else if( oldls && !ls )
	    y <= y + 1'b1;
	else
	    y <= y;

    reg[ 10:0 ] addr1;
    reg we1;
    reg[ 6:0 ] charcode;
    reg[ 7:0 ] attr;
    wire[ 10:0 ] screenaddr = { y[ 9:5 ], x[ 10:5 ] };
    wire odd = x[ 4 ];
    always @( posedge clk ) begin
	addr1 <= x[ 10:0 ];
	we1 <= !x[ 11 ];
	charcode <= y < 11'h380 ? ( odd ? char1[ screenaddr ] : char0[ screenaddr ] ) : 7'h20;
	attr <= y < 11'h380 ? ( odd ? attr1[ screenaddr ] : attr0[ screenaddr ] ) : 7'h00;
    end;

    reg[ 10:0 ] addr2;
    reg we2;
    reg[ 3:0 ] pixval2;
    reg[ 7:0 ] attr2;
    always @( posedge clk ) begin
	addr2 <= addr1;
	we2 <= we1;
	attr2 <= attr;
	pixval2 = font[ { charcode[ 6:0 ], y[ 4:0 ], addr1[ 3:0 ] } ];
    end

    reg[ 10:0 ] addr3;
    reg we3;
    reg[ 3:0 ] fgr, fgg, fgb, bgr, bgg, bgb;
    wire[ 3:0 ] full = pixval2[ 3:0 ];
    wire[ 3:0 ] half = { 0, pixval2[ 3:1 ] };
    always @( posedge clk ) begin
	addr3 <= addr2;
	we3 <= we2;
	fgr[ 3:0 ] <= attr2[ 0 ] ? ( attr2[ 3 ] ? pixval2 :
				     { 1'b0, pixval2[ 3:1 ] } ) :
		      attr2[ 3 ] ? { 2'b0, pixval2[ 3:2 ] } : 4'b0000;
	fgg[ 3:0 ] <= attr2[ 1 ] ? ( attr2[ 3 ] ? pixval2 :
				     { 1'b0, pixval2[ 3:1 ] } ) :
		      attr2[ 3 ] ? { 2'b0, pixval2[ 3:2 ] } : 4'b0000;
	fgb[ 3:0 ] <= attr2[ 2 ] ? ( attr2[ 3 ] ? pixval2 :
				     { 1'b0, pixval2[ 3:1 ] } ) :
		      attr2[ 3 ] ? { 2'b0, pixval2[ 3:2 ] } : 4'b0000;
	bgr[ 3:0 ] <= attr2[ 4 ] ? ( attr2[ 7 ] ? ~pixval2 :
				     { 1'b0, ~pixval2[ 3:1 ] } ) :
		      attr2[ 7 ] ? { 2'b0, ~pixval2[ 3:2 ] } : 4'b0000;
	bgg[ 3:0 ] <= attr2[ 5 ] ? ( attr2[ 7 ] ? ~pixval2 :
				     { 1'b0, ~pixval2[ 3:1 ] } ) :
		      attr2[ 7 ] ? { 2'b0, ~pixval2[ 3:2 ] } : 4'b0000;
	bgb[ 3:0 ] <= attr2[ 6 ] ? ( attr2[ 7 ] ? ~pixval2 :
				     { 1'b0, ~pixval2[ 3:1 ] } ) :
		      attr2[ 7 ] ? { 2'b0, ~pixval2[ 3:2 ] } : 4'b0000;
    end;

    wire[ 3:0 ] rmix, gmix, bmix;
    assign rmix = fgr + bgr;
    assign gmix = fgg + bgg;
    assign bmix = fgb + bgb;
    always @( posedge clk ) begin
        sladdr <= addr3;
        slwe <= we3;
        rdata[ 7:0 ] <= { rmix, rmix };
        gdata[ 7:0 ] <= { gmix, gmix };
        bdata[ 7:0 ] <= { bmix, bmix };
    end;
endmodule

module wishbone_char( input bitclk, output r, g, b, c,
		      input RST_I, input CLK_I, input[ 31:2 ] ADR_I,
		      input[ 31:0 ] DAT_I, output[ 31:0 ] DAT_O,
		      input WE_I, input[ 3:0 ] SEL_I, input STB_I,
		      output reg ACK_O, input CYC_I );

    wire[ 10:0 ] sladdr;
    wire[ 7:0 ] rdata;
    wire[ 7:0 ] gdata;
    wire[ 7:0 ] bdata;
    wire linesync;
    wire framesync;
    wire slwe;
    fpc_hdmi _hdmi( bitclk, r, g, b, c,
		    CLK_I, sladdr, rdata[ 7:0 ], gdata[ 7:0 ], bdata[ 7:0 ],
		    slwe, slwe, slwe, linesync, framesync );

    wire[ 10:0 ] addr;
    wire[ 31:0 ] wdata;
    reg[ 31:0 ] data;
    wire write = CYC_I & STB_I & WE_I;
    chargen _chargen( CLK_I, linesync, framesync,
		      ADR_I[ 12:2 ], DAT_I, DAT_O,
	              { write & SEL_I[ 3 ], write & SEL_I[ 2 ],
			write & SEL_I[ 1 ], write & SEL_I[ 0 ] },
		      sladdr, rdata, gdata, bdata, slwe );

    reg waitstate;
    always @( posedge CLK_I ) begin
	waitstate <= CYC_I && STB_I && !WE_I && !waitstate;
	ACK_O <= CYC_I & STB_I & ( WE_I || waitstate );
    end
endmodule
