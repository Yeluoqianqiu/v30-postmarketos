/* Rasterize UTF-8 SMS into a 48px alpha strip using the installed CJK font. */
#include <ft2build.h>
#include FT_FREETYPE_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define HEIGHT 48
#define MAX_BYTES 65536
#define FONT "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc"

int main(void)
{
    static unsigned char input[MAX_BYTES + 1];
    static uint32_t text[MAX_BYTES];
    size_t len = fread(input, 1, sizeof(input), stdin);
    if(!len || len > MAX_BYTES || ferror(stdin)) return 1;
    size_t count = 0;
    for(size_t i = 0; i < len;) {
        uint32_t c = input[i++];
        unsigned extra = 0;
        if(c >= 0xf0 && c <= 0xf4) { c &= 7; extra = 3; }
        else if(c >= 0xe0 && c <= 0xef) { c &= 15; extra = 2; }
        else if(c >= 0xc2 && c <= 0xdf) { c &= 31; extra = 1; }
        else if(c >= 0x80) return 1;
        if(extra > len - i) return 1;
        for(unsigned n = 0; n < extra; n++) {
            unsigned next = input[i++];
            if((next & 0xc0) != 0x80) return 1;
            c = (c << 6) | (next & 63);
        }
        if(c > 0x10ffff || (c >= 0xd800 && c <= 0xdfff)) return 1;
        text[count++] = c;
    }

    FT_Library library;
    FT_Face face;
    if(FT_Init_FreeType(&library) || FT_New_Face(library, FONT, 2, &face) ||
       FT_Set_Pixel_Sizes(face, 0, 34)) {
        fputs("Cannot load the installed CJK font\n", stderr);
        return 1;
    }

    unsigned width = 8;
    for(size_t i = 0; i < count; i++) {
        FT_ULong c = (FT_ULong)text[i];
        if(!FT_Get_Char_Index(face, c)) c = 0xfffd;
        if(FT_Load_Char(face, c, FT_LOAD_DEFAULT)) return 1;
        unsigned advance = (unsigned)((face->glyph->advance.x + 32) >> 6);
        width += advance > 0 ? advance : 1;
    }
    unsigned char *pixels = calloc(width, HEIGHT);
    if(!pixels) return 1;
    unsigned left = 4;
    for(size_t i = 0; i < count; i++) {
        FT_ULong c = (FT_ULong)text[i];
        if(!FT_Get_Char_Index(face, c)) c = 0xfffd;
        if(FT_Load_Char(face, c, FT_LOAD_RENDER)) return 1;
        FT_GlyphSlot glyph = face->glyph;
        FT_Bitmap *bitmap = &glyph->bitmap;
        if(bitmap->rows && (bitmap->pixel_mode != FT_PIXEL_MODE_GRAY || bitmap->pitch < 0)) return 1;
        for(unsigned row = 0; row < bitmap->rows; row++) {
            int y = 38 - glyph->bitmap_top + (int)row;
            if(y < 0 || y >= HEIGHT) continue;
            for(unsigned col = 0; col < bitmap->width; col++) {
                int x = (int)left + glyph->bitmap_left + (int)col;
                if(x < 0 || x >= (int)width) continue;
                unsigned char alpha = bitmap->buffer[row * (unsigned)bitmap->pitch + col];
                unsigned char *dest = pixels + (size_t)y * width + (unsigned)x;
                if(alpha > *dest) *dest = alpha;
            }
        }
        unsigned advance = (unsigned)((glyph->advance.x + 32) >> 6);
        left += advance > 0 ? advance : 1;
    }
    uint32_t size = width;
    int ok = fwrite(&size, sizeof(size), 1, stdout) == 1 &&
             fwrite(pixels, width, HEIGHT, stdout) == HEIGHT && fflush(stdout) == 0;
    free(pixels);
    FT_Done_Face(face);
    FT_Done_FreeType(library);
    return ok ? 0 : 1;
}
