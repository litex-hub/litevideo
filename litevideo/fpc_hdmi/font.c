#include <stdio.h>
#include <string.h>
#include <math.h>

#include <ft2build.h>
#include FT_FREETYPE_H

unsigned char font[ 0x80 ][ 0x20 ][ 0x10 ]; /* cccccccyyyyyxxxx */

void draw_bitmap( int n, FT_Bitmap* bitmap, FT_Int x, FT_Int y ) {

    FT_Int i, j, p, q;
    FT_Int x_max = x + bitmap->width;
    FT_Int y_max = y + bitmap->rows;

    for( i = x, p = 0; i < x_max; i++, p++ ) {
	for ( j = y, q = 0; j < y_max; j++, q++ ) {
	    if ( i < 0 || j < 0 || i >= 0x10 || j >= 0x20 )
		continue;

	    font[ n ][ j ][ i ] = bitmap->buffer[ q * bitmap->width + p ] >> 4;
	}
    }
}

void show_font( void ) {

    unsigned char *p;

    for( p = &font[ 0 ][ 0 ][ 0 ]; p < &font[ 0x80 ][ 0 ][ 0 ]; p++ )
	printf( "%X\n", *p );
}

extern int main( int argc, char *argv[] ) {

    FT_Library library;
    FT_Face face;
    FT_GlyphSlot slot;
    char *filename;
    int i, x, y;

    if ( argc != 2 ) {
	fprintf( stderr, "usage: %s font\n", argv[ 0 ] );
	return 1;
    }

    filename = argv[ 1 ];

    FT_Init_FreeType( &library );
    FT_New_Face( library, filename, 0, &face );

    FT_Set_Char_Size( face, 27 * 64, 0, 72, 0 );
    
    slot = face->glyph;

    for( i = 0x21; i < 0x7F; i++ ) {
	if( FT_Load_Char( face, i, FT_LOAD_RENDER ) )
	    continue;

	draw_bitmap( i, &slot->bitmap, slot->bitmap_left,
		     0x18 - slot->bitmap_top );
    }

    for( y = 0; y < 0x20; y++ )
	for( x = 0; x < 0x10; x++ )
	    font[ 0x01 ][ y ][ x ] = x ^ y ? 0x0 : 0xF;
    
    for( y = 0; y < 0x20; y++ )
	for( x = 0; x < 0x20; x++ ) {
	    int fill;
	    
	    if( ( x + 1 ) * ( x + 1 ) + ( y + 1 ) * ( y + 1 ) < 0x400 )
		fill = 0x0F;
	    else if( x * x + y * y >= 0x400 )
		fill = 0;
	    else {
		int dx, dy;

		fill = 0;
		
		for( dx = 0; dx < 4; dx++ )
		    for( dy = 0; dy < 4; dy++ )
			fill += ( ( x * 4 + dx ) * ( x * 4 + dx ) +
				  ( y * 4 + dy ) * ( y * 4 + dy ) < 0x4000 );

		if( fill > 0x0F )
		    fill = 0x0F;
	    }

	    font[ 2 + ( x < 0x10 ) ][ 0x1F - y ][ 0x0F - ( x & 0x0F ) ] = fill;
	    font[ 4 + ( x >= 0x10 ) ][ 0x1F - y ][ x & 0x0F ] = fill;
	    font[ 6 + ( x < 0x10 ) ][ y ][ 0x0F - ( x & 0x0F ) ] = fill;
	    font[ 8 + ( x >= 0x10 ) ][ y ][ x & 0x0F ] = fill;
	}

    for( y = 0; y <= 0x10; y++ )
	for( x = 0x07; x <= 0x08; x++ ) {
	    font[ 0x0A ][ y ][ x ] = 0x0F;
	    font[ 0x0D ][ y ][ x ] = 0x0F;
	    font[ 0x0E ][ y ][ x ] = 0x0F;
	    font[ 0x14 ][ y ][ x ] = 0x0F;
	    font[ 0x15 ][ y ][ x ] = 0x0F;
	    font[ 0x16 ][ y ][ x ] = 0x0F;
	    font[ 0x18 ][ y ][ x ] = 0x0F;
	}
    
    for( y = 0x0F; y < 0x20; y++ )
	for( x = 0x07; x <= 0x08; x++ ) {
	    font[ 0x0B ][ y ][ x ] = 0x0F;
	    font[ 0x0C ][ y ][ x ] = 0x0F;
	    font[ 0x0E ][ y ][ x ] = 0x0F;
	    font[ 0x14 ][ y ][ x ] = 0x0F;
	    font[ 0x15 ][ y ][ x ] = 0x0F;
	    font[ 0x17 ][ y ][ x ] = 0x0F;
	    font[ 0x18 ][ y ][ x ] = 0x0F;
	}

    for( x = 0; x <= 0x08; x++ )
	for( y = 0x0F; y <= 0x10; y++ ) {
	    font[ 0x0A ][ y ][ x ] = 0x0F;
	    font[ 0x0B ][ y ][ x ] = 0x0F;
	    font[ 0x0E ][ y ][ x ] = 0x0F;
	    font[ 0x11 ][ y ][ x ] = 0x0F;
	    font[ 0x15 ][ y ][ x ] = 0x0F;
	    font[ 0x16 ][ y ][ x ] = 0x0F;
	    font[ 0x17 ][ y ][ x ] = 0x0F;
	}
    
    for( x = 0x07; x < 0x10; x++ )
	for( y = 0x0F; y <= 0x10; y++ ) {
	    font[ 0x0C ][ y ][ x ] = 0x0F;
	    font[ 0x0D ][ y ][ x ] = 0x0F;
	    font[ 0x0E ][ y ][ x ] = 0x0F;
	    font[ 0x11 ][ y ][ x ] = 0x0F;
	    font[ 0x14 ][ y ][ x ] = 0x0F;
	    font[ 0x16 ][ y ][ x ] = 0x0F;
	    font[ 0x17 ][ y ][ x ] = 0x0F;
	}

    font[ 0x1E ][ 0x0F ][ 0x07 ] = 0x0F;
    font[ 0x1E ][ 0x0F ][ 0x08 ] = 0x0F;
    font[ 0x1E ][ 0x10 ][ 0x07 ] = 0x0F;
    font[ 0x1E ][ 0x10 ][ 0x08 ] = 0x0F;
    
    for( y = 0; y < 0x20; y++ )
	for( x = 0; x < 0x10; x++ )
	    font[ 0x7F ][ y ][ x ] = y >> 1;
    
    show_font();

    FT_Done_Face( face );
    FT_Done_FreeType( library );

    return 0;
}
