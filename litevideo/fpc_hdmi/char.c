#include <stdio.h>

static unsigned char c[ 0x20 ][ 0x80 ], a[ 0x20 ][ 0x80 ];

static void put( int y, int x, int ch, int fg, int bg ) {

    c[ y ][ x ] = ch;
    a[ y ][ x ] = ( bg << 4 ) | fg;
}

static void putm( int y, int x, char *p, int fg, int bg ) {

    while( *p )
	put( y, x++, *p++, fg, bg );
}

extern int main( void ) {

    FILE *f;
    int x, y;

    for( x = 0; x < 0x80; x++ )
	for( y = 0; y < 0x20; y++ )
	    put( y, x, 0x20, 0x07, 0x00 );

    for( x = 4; x < 20; x++ )
	for( y = 0; y < 2; y++ )
	    put( y, x, 0x20, 0x00, 0x09 );
    for( x = 4; x < 16; x++ )
	for( y = 4; y < 6; y++ )
	    put( y, x, 0x20, 0x00, 0x09 );
    for( x = 4; x < 8; x++ )
	for( y = 2; y < 10; y++ )
	    put( y, x, 0x20, 0x00, 0x09 );

    for( x = 24; x < 40; x++ )
	for( y = 0; y < 2; y++ )
	    put( y, x, 0x20, 0x00, 0x02 );
    for( x = 24; x < 40; x++ )
	for( y = 4; y < 6; y++ )
	    put( y, x, 0x20, 0x00, 0x02 );
    for( x = 24; x < 28; x++ )
	for( y = 2; y < 10; y++ )
	    put( y, x, 0x20, 0x00, 0x02 );
    for( x = 36; x < 40; x++ )
	for( y = 2; y < 4; y++ )
	    put( y, x, 0x20, 0x00, 0x02 );
    put( 0, 38, 0x04, 0x02, 0x00 );
    put( 0, 39, 0x05, 0x02, 0x00 );
    put( 5, 38, 0x08, 0x02, 0x00 );
    put( 5, 39, 0x09, 0x02, 0x00 );
    
    for( x = 44; x < 60; x++ )
	for( y = 0; y < 2; y++ )
	    put( y, x, 0x20, 0x00, 0x0C );
    for( x = 44; x < 60; x++ )
	for( y = 8; y < 10; y++ )
	    put( y, x, 0x20, 0x00, 0x0C );
    for( x = 44; x < 48; x++ )
	for( y = 2; y < 8; y++ )
	    put( y, x, 0x20, 0x00, 0x0C );
    for( x = 56; x < 60; x++ ) {
	put( 2, x, 0x20, 0x00, 0x0C );
	put( 7, x, 0x20, 0x00, 0x0C );
    }
    put( 0, 44, 0x02, 0x0C, 0x00 );
    put( 0, 45, 0x03, 0x0C, 0x00 );
    put( 9, 44, 0x06, 0x0C, 0x00 );
    put( 9, 45, 0x07, 0x0C, 0x00 );
    put( 0, 58, 0x04, 0x0C, 0x00 );
    put( 0, 59, 0x05, 0x0C, 0x00 );
    put( 9, 58, 0x08, 0x0C, 0x00 );
    put( 9, 59, 0x09, 0x0C, 0x00 );

    for( x = 64; x < 72; x++ )
	for( y = 4; y < 6; y++ )
	    put( y, x, 0x20, 0x00, 0x07 );

    for( x = 76; x < 80; x++ )
	for( y = 0; y < 10; y++ ) {
	    static int col[] = { 12, 13, 9, 11, 10, 14, 12, 13, 9, 11, 10 };
	    put( y, x, 0x7F, col[ y + 1 ], col[ y ] );
	    put( y, x + 8, 0x7F, col[ y + 1 ], col[ y ] );
	    put( y, x + 16, 0x7F, col[ y + 1 ], col[ y ] );
	}

    putm( 11, 4, "Free Permutable Computer", 0x07, 0x00 );
    putm( 11, 85, "gtw@gnu.org", 0x07, 0x00 );
    
    f = fopen( "char0.hex", "w" );
    for( y = 0; y < 0x20; y++ )
	for( x = 0; x < 0x80; x += 2 )
	    fprintf( f, "%02X\n", c[ y ][ x ] );
    fclose( f );
	
    f = fopen( "attr0.hex", "w" );
    for( y = 0; y < 0x20; y++ )
	for( x = 0; x < 0x80; x += 2 )
	    fprintf( f, "%02X\n", a[ y ][ x ] );
    fclose( f );
    
    f = fopen( "char1.hex", "w" );
    for( y = 0; y < 0x20; y++ )
	for( x = 1; x < 0x80; x += 2 )
	    fprintf( f, "%02X\n", c[ y ][ x ] );
    fclose( f );
	
    f = fopen( "attr1.hex", "w" );
    for( y = 0; y < 0x20; y++ )
	for( x = 1; x < 0x80; x += 2 )
	    fprintf( f, "%02X\n", a[ y ][ x ] );
    fclose( f );
    
    return 0;
}
