import os
from pathlib import Path
from typing import Optional

from fontTools.ttLib import TTFont
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.qu2cuPen import Qu2CuPen

from .converter_interface import ConverterInterface


class FonttoolsConverter(ConverterInterface):
    """
    Converter for font formats using fontTools.
    Supports conversions between TTF, OTF, WOFF, and WOFF2 formats.

    Conversion capabilities:
    - TTF  <-> WOFF, WOFF2 (re-wrap, no outline change)
    - OTF  <-> WOFF, WOFF2 (re-wrap, no outline change)
    - TTF  <-> OTF         (outline conversion: quadratic <-> cubic)
    - WOFF <-> WOFF2       (re-compress)
    """

    supported_input_formats: set = {
        'ttf',
        'otf',
        'woff',
        'woff2',
    }
    supported_output_formats: set = {
        'ttf',
        'otf',
        'woff',
        'woff2',
    }

    # Map file extensions to the fontTools flavor value.
    # TTF/OTF are "plain" (flavor=None); WOFF/WOFF2 are wrapped flavors.
    _flavor_map = {
        'ttf': None,
        'otf': None,
        'woff': 'woff',
        'woff2': 'woff2',
    }

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        """
        Initialize fontTools converter.

        Args:
            input_file: Path to the input font file
            output_dir: Directory where the converted file will be saved
            input_type: Input file format (e.g., 'ttf', 'otf', 'woff', 'woff2')
            output_type: Output file format (e.g., 'ttf', 'otf', 'woff', 'woff2')
        """
        super().__init__(input_file, output_dir, input_type, output_type)

    def can_convert(self) -> bool:
        """
        Check if the input file can be converted to the output format.

        Returns:
            True if conversion is possible, False otherwise.
        """
        input_fmt = self.input_type.lower()
        output_fmt = self.output_type.lower()

        if input_fmt not in self.supported_input_formats:
            return False
        if output_fmt not in self.supported_output_formats:
            return False

        return True

    @classmethod
    def get_formats_compatible_with(cls, format_type: str) -> set:
        """
        Get the set of compatible output formats for a given input format.

        Args:
            format_type: The input format to check compatibility for.

        Returns:
            Set of compatible output formats.
        """
        fmt = format_type.lower()
        if fmt not in cls.supported_input_formats:
            return set()
        return cls.supported_output_formats - {fmt}

    @staticmethod
    def _has_cubic_outlines(font: TTFont) -> bool:
        """Return True if the font contains CFF/CFF2 (cubic) outlines."""
        return 'CFF ' in font or 'CFF2' in font

    @staticmethod
    def _has_quadratic_outlines(font: TTFont) -> bool:
        """Return True if the font contains glyf (quadratic) outlines."""
        return 'glyf' in font

    def _needs_outline_conversion(self, font: TTFont) -> bool:
        """
        Determine whether outline conversion (cubic <-> quadratic) is needed.

        - If the output is OTF we need cubic outlines (CFF).
        - If the output is TTF/WOFF/WOFF2 we need quadratic outlines (glyf).
        - WOFF/WOFF2 can wrap *either* outline type, but conventionally
          they keep whatever the source has. Only when explicitly targeting
          TTF or OTF do we force an outline change.

        Returns:
            True if the outlines must be converted.
        """
        target = self.output_type.lower()

        if target == 'otf' and not self._has_cubic_outlines(font):
            return True
        if target == 'ttf' and not self._has_quadratic_outlines(font):
            return True

        return False

    def _convert_outlines_to_quadratic(self, font: TTFont) -> TTFont:
        """
        Convert CFF (cubic) outlines to glyf (quadratic TrueType) outlines.

        Uses fontTools' Cu2QuPen for accurate cubic-to-quadratic approximation.

        Returns:
            A new TTFont with quadratic outlines.
        """
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        from fontTools.pens.recordingPen import DecomposingRecordingPen
        from fontTools.ttLib.tables._g_l_y_f import table__g_l_y_f, Glyph
        from fontTools.ttLib.tables._l_o_c_a import table__l_o_c_a

        glyph_order = font.getGlyphOrder()
        glyph_set = font.getGlyphSet()

        # Build a new font preserving all non-outline tables
        new_font = TTFont()
        _skip = {'CFF ', 'CFF2', 'glyf', 'loca'}
        for tag in font.keys():
            if tag not in _skip:
                new_font[tag] = font[tag]

        new_font['loca'] = table__l_o_c_a()
        new_font['glyf'] = table__g_l_y_f()
        new_font['glyf'].glyphs = {}
        new_font['glyf'].glyphOrder = glyph_order
        new_font.setGlyphOrder(glyph_order)

        # Draw each glyph through Cu2QuPen into a TrueType glyph pen
        for glyph_name in glyph_order:
            tt_pen = TTGlyphPen(None)
            try:
                cu2qu_pen = Cu2QuPen(tt_pen, max_err=1.0, reverse_direction=True)
                decomposing_pen = DecomposingRecordingPen(glyph_set)
                glyph_set[glyph_name].draw(decomposing_pen)
                decomposing_pen.replay(cu2qu_pen)
                new_font['glyf'][glyph_name] = tt_pen.glyph()
            except Exception:
                new_font['glyf'][glyph_name] = Glyph()

        new_font['head'].indexToLocFormat = 0
        new_font.recalcBBoxes = True
        return new_font

    def _convert_outlines_to_cubic(self, font: TTFont) -> TTFont:
        """
        Convert glyf (quadratic TrueType) outlines to CFF (cubic PostScript) outlines.

        Uses fontTools' Qu2CuPen for accurate quadratic-to-cubic conversion,
        and FontBuilder to construct a valid CFF-based OTF font.

        Returns:
            A new TTFont with CFF (cubic) outlines.
        """
        from fontTools.fontBuilder import FontBuilder
        from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen

        glyph_order = font.getGlyphOrder()
        glyph_set = font.getGlyphSet()
        hmtx = font['hmtx'].metrics
        upm = font['head'].unitsPerEm

        # Step 1: Record outlines, converting quadratic to cubic via Qu2CuPen
        cubic_recordings: dict[str, RecordingPen] = {}
        for glyph_name in glyph_order:
            decomposed = DecomposingRecordingPen(glyph_set)
            glyph_set[glyph_name].draw(decomposed)

            cubic_rec = RecordingPen()
            qu2cu_pen = Qu2CuPen(cubic_rec, max_err=1.0, reverse_direction=False)
            decomposed.replay(qu2cu_pen)
            cubic_recordings[glyph_name] = cubic_rec

        # Step 2: Build a new CFF-based font using FontBuilder
        fb = FontBuilder(upm, isTTF=False)
        fb.setupGlyphOrder(glyph_order)
        fb.setupCharacterMap(font.getBestCmap() or {})

        # Build charstring dicts for CFF by drawing into T2CharStringPens
        from fontTools.pens.t2CharStringPen import T2CharStringPen

        charstrings_dict: dict = {}
        for glyph_name in glyph_order:
            pen = T2CharStringPen(hmtx[glyph_name][0], None)
            cubic_recordings[glyph_name].replay(pen)
            charstrings_dict[glyph_name] = pen.getCharString()

        # Get PostScript name for CFF
        ps_name = 'Unknown'
        name_table = font.get('name')
        if name_table:
            for plat_id, enc_id, lang_id in [(3, 1, 0x0409), (1, 0, 0)]:
                rec = name_table.getName(6, plat_id, enc_id, lang_id)
                if rec:
                    ps_name = rec.toStr()
                    break

        fb.setupCFF(ps_name, {}, charstrings_dict, {})

        fb.setupHorizontalMetrics(
            {name: (hmtx[name][0], hmtx[name][1]) for name in glyph_order}
        )

        # Copy key metadata tables from the source font
        hhea = font.get('hhea')
        if hhea:
            fb.setupHorizontalHeader(
                ascent=hhea.ascent,
                descent=hhea.descent,
                lineGap=hhea.lineGap,
            )

        # Setup name table from source
        name_dict = {}
        _name_ids = {
            0: 'copyright', 1: 'familyName', 2: 'styleName',
            3: 'uniqueFontIdentifier', 4: 'fullName', 5: 'version',
            6: 'psName', 7: 'trademark', 8: 'manufacturer',
            9: 'designer', 10: 'description', 11: 'vendorURL',
            12: 'designerURL', 13: 'licenseDescription', 14: 'licenseInfoURL',
        }
        if name_table:
            for name_id, key in _name_ids.items():
                rec = name_table.getName(name_id, 3, 1, 0x0409) or name_table.getName(name_id, 1, 0, 0)
                if rec:
                    name_dict[key] = rec.toStr()
        if 'familyName' not in name_dict:
            name_dict['familyName'] = ps_name
        if 'styleName' not in name_dict:
            name_dict['styleName'] = 'Regular'
        fb.setupNameTable(name_dict)

        # Setup OS/2 table from source
        os2 = font.get('OS/2')
        if os2:
            fb.setupOS2(
                sTypoAscender=os2.sTypoAscender,
                sTypoDescender=os2.sTypoDescender,
                sTypoLineGap=os2.sTypoLineGap,
            )
        else:
            fb.setupOS2()

        fb.setupPost()

        return fb.font

    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """
        Convert the input font file to the output format using fontTools.

        Args:
            overwrite: Whether to overwrite existing output file (default: True)
            quality: Not applicable for font formats, ignored.

        Returns:
            List containing the path to the converted output file.

        Raises:
            FileNotFoundError: If input file doesn't exist.
            ValueError: If the conversion is not supported.
            RuntimeError: If conversion fails.
        """
        if not self.can_convert():
            raise ValueError(
                f"Conversion from {self.input_type} to {self.output_type} is not supported."
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        # Generate output filename
        input_filename = Path(self.input_file).stem
        output_file = os.path.join(
            self.output_dir, f"{input_filename}.{self.output_type}"
        )

        # Check if output file exists and overwrite is False
        if not overwrite and os.path.exists(output_file):
            return [output_file]

        try:
            font = TTFont(self.input_file)

            # Determine target flavor (None for ttf/otf, 'woff'/'woff2' for web fonts)
            target_flavor = self._flavor_map.get(self.output_type.lower())

            # Handle outline conversion when crossing TTF <-> OTF boundary
            if self._needs_outline_conversion(font):
                if self.output_type.lower() == 'ttf':
                    font = self._convert_outlines_to_quadratic(font)
                elif self.output_type.lower() == 'otf':
                    font = self._convert_outlines_to_cubic(font)

            font.flavor = target_flavor
            font.save(output_file)
            font.close()

            if not os.path.exists(output_file):
                raise RuntimeError(f"Output file was not created: {output_file}")

            return [output_file]

        except (ValueError, RuntimeError):
            raise
        except Exception as e:
            raise RuntimeError(f"Font conversion failed: {str(e)}")
