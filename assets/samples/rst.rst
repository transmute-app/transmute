=============================
Main Document Title
=============================
This is the main title, typically underlined and overlined with the same character (e.g., '=', as shown here).

Section Title
-------------
Subtitles use different single characters (like '-', '~', '^') for underlining. The length of the underline should match the length of the text.

Paragraphs are just blocks of text separated by blank lines.

You can format text in several ways:

*   *Italic* text is created with single asterisks.
*   **Bold** text is created with double asterisks.
*   ``Inline code`` is created with double backquotes.

Lists are easy to make:

*   Bullet points use '*', '+', or '-' followed by a space.
*   Items can span multiple lines.

1.  Ordered lists use numbers or letters followed by a period or parenthesis.
2.  Auto-enumerated lists also work.

External links can be created in a few ways:

*   A naked link: https://docutils.sourceforge.io/rst.html.
*   An embedded URI: `Microsoft <https://microsoft.com>`_.

For preformatted text, such as code samples, end the preceding paragraph with a double colon (::) and then indent the code block by at least four spaces:

An example::

    Whitespace, newlines, blank lines, and all kinds of markup is preserved in literal blocks.

    This entire block is indented and monospaced.

You can also use directives for specific elements like notes, warnings, or including external content.

.. note::
   This is a note block, created using a '..' followed by the directive name. The content is indented.

.. image:: https://sourceforge.io
   :alt: reStructuredText Logo

