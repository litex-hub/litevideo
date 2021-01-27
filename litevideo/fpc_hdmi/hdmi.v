//
// hdmi.v
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

module fpc_hdmi( input bitclk,
		 output r, g, b, c,
		 input clk, input[ 10:0 ] addr, input[ 7:0 ] rdata,
		 input[ 7:0 ] gdata, input[ 7:0 ] bdata, input rwe,
		 input gwe, input bwe,
		 output linesync, output framesync );

    // 1600x900 (400 MHz -> 49 Hz)
    parameter WIDTH = 1600;
    parameter HEIGHT = 900;
    parameter HSTART = 1648;
    parameter HEND = 1680;
    parameter HTOTAL = 1760;
    parameter VSTART = 903;
    parameter VEND = 908;
    parameter VTOTAL = 926;
    parameter HBITS = 11;
    parameter VBITS = 10;
    
    // Clock divider
    wire halfclk;
    CLKDIVF div( .CLKI( bitclk ), .RST( 0 ), .ALIGNWD( 0 ),
		 .CDIVX( halfclk ) );
    
    // Derived pixel clock
    reg[ 2:0 ] bitctr = 3'b0;
    reg loadfast;
    reg loadslow;
    reg pixclk;
    
    always @( posedge halfclk ) begin
	bitctr <= bitctr == 3'b100 ? 3'b000 : bitctr + 1'b1;
	loadfast <= bitctr == 3'b011;
	loadslow <= bitctr == 3'b000;      
	pixclk <= bitctr == 3'b000 || bitctr == 3'b011;      
    end
    
    reg[ 10:0 ] sladdr;
    reg[ 7:0 ] slrdata;
    reg[ 7:0 ] slgdata;
    reg[ 7:0 ] slbdata;

    scanlinecol scanliner( clk, addr, rdata, rwe, pixclk, sladdr, slrdata );
    scanlinecol scanlineg( clk, addr, gdata, gwe, pixclk, sladdr, slgdata );
    scanlinecol scanlineb( clk, addr, bdata, bwe, pixclk, sladdr, slbdata );
			       
    // Address generator: output x10/y10
    reg[ HBITS-1:0 ] x10 = 0;
    reg[ VBITS-1:0 ] y10 = 0;
    wire[ HBITS-1:0 ] newx10;
    wire[ VBITS-1:0 ] newy10;
    wire newline;
    wire newframe;

    assign newline = x10 == HTOTAL - 1;
    assign newframe = newline & ( y10 == VTOTAL - 1 );
    assign newx10 = newline ? 0 : x10 + 1;
    assign newy10 = newframe ? 0 : ( newline ? y10 + 1 : y10 );
    always @( posedge pixclk ) begin
	x10 <= newx10;
	y10 <= newy10;
    end

    assign framesync = y10 == VTOTAL - 1;
		      
    // Sync generator: active20/sync20
    reg hactive20 = 1'b1;
    reg vactive20 = 1'b1;
    reg hsync20 = 1'b0;
    reg vsync20 = 1'b1;

    always @( posedge pixclk ) begin
	sladdr <= newx10;
	if( x10 == 0 ) hactive20 <= 1'b1;
	if( x10 == WIDTH ) hactive20 <= 1'b0;
	if( x10 == HSTART ) hsync20 <= 1'b1;
	if( x10 == HEND ) hsync20 <= 1'b0;
	if( y10 == 0 ) vactive20 <= 1'b1;
	if( y10 == HEIGHT ) vactive20 <= 1'b0;
	if( y10 == VSTART ) vsync20 <= 1'b1;
	if( y10 == VEND ) vsync20 <= 1'b0;
    end

    assign linesync = hactive20;
    
    // Pixel generator: output r/g/bval30/active30/sync30
    reg[ 7:0 ] rval30;
    reg[ 7:0 ] gval30;
    reg[ 7:0 ] bval30;   
    reg hactive30;
    reg vactive30;
    reg hsync30;
    reg vsync30;
    
    always @( posedge pixclk ) begin
	rval30[ 7:0 ] <= slrdata[ 7:0 ];
	gval30[ 7:0 ] <= slgdata[ 7:0 ];
	bval30[ 7:0 ] <= slbdata[ 7:0 ];
	hactive30 <= hactive20;
	hsync30 <= hsync20;
	vactive30 <= vactive20;
	vsync30 <= vsync20;
    end
    
    // 8b10b encoder: output r/g/benc40/active40/sync40
    wire[ 9:0 ] renc40;
    wire[ 9:0 ] genc40;
    wire[ 9:0 ] benc40;
    reg active40;
    reg hsync40;
    reg vsync40;
    
    enc8b10b r8b10b( rval30[ 7:0 ], renc40, pixclk );
    enc8b10b g8b10b( gval30[ 7:0 ], genc40, pixclk );
    enc8b10b b8b10b( bval30[ 7:0 ], benc40, pixclk );

    always @( posedge pixclk ) begin
	active40 <= hactive30 & vactive30;
	hsync40 <= hsync30;
	vsync40 <= vsync30;      
    end
    
    // Control/data encoder: output 10 bit code
    reg[ 9:0 ] rpix;
    reg[ 9:0 ] gpix;
    reg[ 9:0 ] bpix;
    reg[ 9:0 ] cpix;

    always @( posedge pixclk ) begin
	rpix <= active40 ? renc40 : 10'b1101010100;
	gpix <= active40 ? genc40 : 10'b1101010100;
	if( active40 )
	    bpix <= benc40;      
	else case( {hsync40,vsync40} )
	     2'b00: bpix <= 10'b1101010100;	     
	     2'b01: bpix <= 10'b0101010100;	     
	     2'b10: bpix <= 10'b0010101011;	     
	     2'b11: bpix <= 10'b1010101011;	     
	     endcase	     
	cpix <= 10'b1111100000;      
    end

    pixshift pixshiftr( rpix, pixclk, loadfast, loadslow, halfclk, bitclk, r );
    pixshift pixshiftg( gpix, pixclk, loadfast, loadslow, halfclk, bitclk, g );
    pixshift pixshiftb( bpix, pixclk, loadfast, loadslow, halfclk, bitclk, b );
    pixshift pixshiftc( cpix, pixclk, loadfast, loadslow, halfclk, bitclk, c );
endmodule

module pixshift( input[ 9:0 ] bits, input newpix,
		 input loadfast, input loadslow, input halfclk, input bitclk,
		 output bitp );
    reg[ 9:0 ] pbits;
    reg[ 9:0 ] sbits;

    always @( posedge newpix )
	pbits <= bits;

    always @( posedge halfclk )
	sbits <= pbits;
    
    reg[ 15:0 ] statep;
    
    always @( posedge halfclk ) begin
	if( loadfast )
	    statep[ 15:4 ] <= { 2'bxx, sbits };
	else if( loadslow )
	    statep[ 15:4 ] <= { sbits, statep[ 9:8 ] };
	else
	    statep[ 15:4 ] <= { 4'bxxxx, statep[ 15:8 ] };
	statep[ 3:0 ] <= statep[ 7:4 ];
    end

    // ODDRX2F: SCLK, ECLK, RST, D0, D1, D2, D3 -> Q   
    ODDRX2F obp( halfclk, bitclk, 1'b0, 
		 statep[ 0 ], statep[ 1 ], statep[ 2 ], statep[ 3 ], bitp );
endmodule

module enc8b10b( input[ 7:0 ] raw, output reg[ 9:0 ] enc, input clk );
    function[ 2:0 ] countones;
	input[ 3:0 ] val;
	begin
	    case( val )
	    4'b0000: countones = 3'b000;
	    4'b0001: countones = 3'b001;
	    4'b0010: countones = 3'b001;
	    4'b0011: countones = 3'b010;
	    4'b0100: countones = 3'b001;
	    4'b0101: countones = 3'b010;
	    4'b0110: countones = 3'b010;
	    4'b0111: countones = 3'b011;
	    4'b1000: countones = 3'b001;
	    4'b1001: countones = 3'b010;
	    4'b1010: countones = 3'b010;
	    4'b1011: countones = 3'b011;
	    4'b1100: countones = 3'b010;
	    4'b1101: countones = 3'b011;
	    4'b1110: countones = 3'b011;
	    4'b1111: countones = 3'b100;
	    endcase
	end
    endfunction

    wire[ 3:0 ] ones;
    assign ones = 4'b0000 + countones( raw[ 7:4 ] ) + countones( raw[ 3:0 ] );
    
    wire[ 8:0 ] xorv;   
    assign xorv[ 0 ] = raw[ 0 ];
    assign xorv[ 1 ] = xorv[ 0 ] ^ raw[ 1 ];
    assign xorv[ 2 ] = xorv[ 1 ] ^ raw[ 2 ];
    assign xorv[ 3 ] = xorv[ 2 ] ^ raw[ 3 ];
    assign xorv[ 4 ] = xorv[ 3 ] ^ raw[ 4 ];
    assign xorv[ 5 ] = xorv[ 4 ] ^ raw[ 5 ];
    assign xorv[ 6 ] = xorv[ 5 ] ^ raw[ 6 ];
    assign xorv[ 7 ] = xorv[ 6 ] ^ raw[ 7 ];
    assign xorv[ 8 ] = 1;
    
    wire[ 8:0 ] xnorv;
    assign xnorv[ 0 ] = raw[ 0 ];
    assign xnorv[ 1 ] = !( xnorv[ 0 ] ^ raw[ 1 ] );
    assign xnorv[ 2 ] = !( xnorv[ 1 ] ^ raw[ 2 ] );
    assign xnorv[ 3 ] = !( xnorv[ 2 ] ^ raw[ 3 ] );
    assign xnorv[ 4 ] = !( xnorv[ 3 ] ^ raw[ 4 ] );
    assign xnorv[ 5 ] = !( xnorv[ 4 ] ^ raw[ 5 ] );
    assign xnorv[ 6 ] = !( xnorv[ 5 ] ^ raw[ 6 ] );
    assign xnorv[ 7 ] = !( xnorv[ 6 ] ^ raw[ 7 ] );
    assign xnorv[ 8 ] = 0;

    wire[ 8:0 ] word;   
    assign word = ones > 4'd4 || ( ones == 4'd4 && !raw[ 0 ] ) ? xnorv : xorv;

    wire[ 8:0 ] invword;
    assign invword[ 8 ] = word[ 8 ];
    assign invword[ 7:0 ] = ~word[ 7:0 ];   
    
    // FIXME apply DC balance 
    //   wire [ 3:0 ] wordones;
    //   assign wordones = 4'b0000 + countones( word[ 7:4 ] ) + countones( word[ 3:0 ] );

    always @( posedge clk ) begin
	enc[ 8:0 ] <= word[ 8 ] ? word : invword;
	enc[ 9 ] <= ~word[ 8 ];
	
	// FIXME apply DC balance 
	//      imbalance <= FIXME;
    end
endmodule

module scanlinecol( input clk, input[ 10:0 ] addr, input[ 7:0 ] data, input we,
		    input rclk, input[ 10:0 ] raddr, output[ 7:0 ] rdata );
    DP16KD #( .DATA_WIDTH_A( 9 ), .DATA_WIDTH_B( 9 ),
	      .CLKAMUX( "CLKA" ), .CLKBMUX( "CLKB" ),
	      .WRITEMODE_A( "READBEFOREWRITE" ),
	      .WRITEMODE_B( "READBEFOREWRITE" ),
	      .GSR( "AUTO" )
    ) scanline( .CLKA( clk ), .WEA( we ), .CEA( 1 ), .OCEA( 0 ), .RSTA( 0 ),
		.ADA3( addr[ 0 ] ),
		.ADA4( addr[ 1 ] ),
		.ADA5( addr[ 2 ] ),
		.ADA6( addr[ 3 ] ),
		.ADA7( addr[ 4 ] ),
		.ADA8( addr[ 5 ] ),
		.ADA9( addr[ 6 ] ),
		.ADA10( addr[ 7 ] ),
		.ADA11( addr[ 8 ] ),
		.ADA12( addr[ 9 ] ),
		.ADA13( addr[ 10 ] ),
		.DIA0( data[ 0 ] ),
		.DIA1( data[ 1 ] ),
		.DIA2( data[ 2 ] ),
		.DIA3( data[ 3 ] ),
		.DIA4( data[ 4 ] ),
		.DIA5( data[ 5 ] ),
		.DIA6( data[ 6 ] ),
		.DIA7( data[ 7 ] ),
		.CLKB( rclk ), .WEB( 0 ), .CEB( 1 ), .OCEB( 1 ), .RSTB( 0 ),
		.ADB3( raddr[ 0 ] ),
		.ADB4( raddr[ 1 ] ),
		.ADB5( raddr[ 2 ] ),
		.ADB6( raddr[ 3 ] ),
		.ADB7( raddr[ 4 ] ),
		.ADB8( raddr[ 5 ] ),
		.ADB9( raddr[ 6 ] ),
		.ADB10( raddr[ 7 ] ),
		.ADB11( raddr[ 8 ] ),
		.ADB12( raddr[ 9 ] ),
		.ADB13( raddr[ 10 ] ),
		.DOB0( rdata[ 0 ] ),
		.DOB1( rdata[ 1 ] ),
		.DOB2( rdata[ 2 ] ),
		.DOB3( rdata[ 3 ] ),
		.DOB4( rdata[ 4 ] ),
		.DOB5( rdata[ 5 ] ),
		.DOB6( rdata[ 6 ] ),
		.DOB7( rdata[ 7 ] ),
    );	      
endmodule
