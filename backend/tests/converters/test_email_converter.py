import json
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

import converters.email_convert as email_convert_module
from converters.email_convert import EmailConverter


def create_sample_email(tmp_path) -> Path:
    message = EmailMessage()
    message['Subject'] = 'Quarterly Update'
    message['From'] = 'sender@example.com'
    message['To'] = 'recipient@example.com'
    message['Cc'] = 'teammate@example.com'
    message['Reply-To'] = 'reply@example.com'
    message['Date'] = 'Wed, 12 Mar 2026 10:30:00 +0000'
    message['Message-ID'] = '<message-1@example.com>'
    message.set_content('Hello team,\n\nThe report is attached.\n')
    message.add_alternative(
        '<html><body><p>Hello <strong>team</strong>,</p><p>The report is attached.</p></body></html>',
        subtype='html',
    )
    message.add_attachment(
        b'report-bytes',
        maintype='application',
        subtype='octet-stream',
        filename='report.csv',
    )

    input_file = tmp_path / 'message.eml'
    input_file.write_bytes(message.as_bytes())
    return input_file


def create_inline_attachment_email(tmp_path) -> Path:
    message = EmailMessage()
    message['Subject'] = 'Inline Assets'
    message['From'] = 'sender@example.com'
    message['To'] = 'recipient@example.com'
    message.set_content('Fallback body')
    message.add_alternative(
        '<html><body><p>Inline image:</p><img src="cid:logo.gif"><p>See notes.</p></body></html>',
        subtype='html',
    )

    html_part = message.get_payload()[1]
    html_part.add_related(
        b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02L\x01\x00;',
        maintype='image',
        subtype='gif',
        cid='<logo.gif>',
        filename='logo.gif',
        disposition='inline',
    )
    message.add_attachment(
        b'Hello from a text attachment.',
        maintype='text',
        subtype='plain',
        filename='notes.txt',
    )

    input_file = tmp_path / 'inline-message.eml'
    input_file.write_bytes(message.as_bytes())
    return input_file


def test_email_converter_can_convert_supported_formats(tmp_path):
    input_file = create_sample_email(tmp_path)
    converter = EmailConverter(str(input_file), str(tmp_path), 'eml', 'md')

    assert converter.can_convert() is True
    assert 'pdf' in converter.get_formats_compatible_with('eml')
    assert 'json' in converter.get_formats_compatible_with('eml')


def test_msg_converter_can_convert_supported_formats(tmp_path, monkeypatch):
    input_file = tmp_path / 'message.msg'
    input_file.write_bytes(b'msg-placeholder')
    monkeypatch.setattr(email_convert_module, 'extract_msg', SimpleNamespace(Message=object))

    converter = EmailConverter(str(input_file), str(tmp_path), 'msg', 'json')

    assert converter.can_convert() is True
    assert 'pdf' in converter.get_formats_compatible_with('msg')
    assert 'html' in converter.get_formats_compatible_with('msg')


def test_email_to_txt_includes_headers_body_and_attachments(tmp_path):
    input_file = create_sample_email(tmp_path)
    converter = EmailConverter(str(input_file), str(tmp_path), 'eml', 'txt')

    [output_file] = converter.convert()
    content = Path(output_file).read_text(encoding='utf-8')

    assert 'Subject: Quarterly Update' in content
    assert 'From: sender@example.com' in content
    assert 'To: recipient@example.com' in content
    assert 'The report is attached.' in content
    assert 'report.csv (application/octet-stream, 12 bytes)' in content


def test_email_to_markdown_uses_email_structure(tmp_path):
    input_file = create_sample_email(tmp_path)
    converter = EmailConverter(str(input_file), str(tmp_path), 'eml', 'md')

    [output_file] = converter.convert()
    content = Path(output_file).read_text(encoding='utf-8')

    assert content.startswith('# Quarterly Update')
    assert '- From: sender@example.com' in content
    assert '## Body' in content
    assert '## Attachments' in content
    assert 'report.csv' in content


def test_email_to_json_returns_structured_payload(tmp_path):
    input_file = create_sample_email(tmp_path)
    converter = EmailConverter(str(input_file), str(tmp_path), 'eml', 'json')

    [output_file] = converter.convert()
    payload = json.loads(Path(output_file).read_text(encoding='utf-8'))

    assert payload['subject'] == 'Quarterly Update'
    assert payload['to'] == ['recipient@example.com']
    assert payload['cc'] == ['teammate@example.com']
    assert payload['attachments'][0]['filename'] == 'report.csv'


def test_email_to_pdf_creates_pdf_file(tmp_path):
    input_file = create_sample_email(tmp_path)
    converter = EmailConverter(str(input_file), str(tmp_path), 'eml', 'pdf')

    [output_file] = converter.convert()
    header = Path(output_file).read_bytes()[:4]

    assert header == b'%PDF'


def test_email_html_renders_inline_cid_images_and_attachment_previews(tmp_path):
    input_file = create_inline_attachment_email(tmp_path)
    converter = EmailConverter(str(input_file), str(tmp_path), 'eml', 'html')

    [output_file] = converter.convert()
    content = Path(output_file).read_text(encoding='utf-8')

    assert 'src="data:image/gif;base64,' in content
    assert 'notes.txt' in content
    assert 'Hello from a text attachment.' in content


def test_msg_to_json_uses_extract_msg_payload(tmp_path, monkeypatch):
    input_file = tmp_path / 'message.msg'
    input_file.write_bytes(b'msg-placeholder')

    class FakeAttachment:
        longFilename = 'report.xlsx'
        name = 'report.xlsx'
        shortFilename = 'REPORT~1.XLSX'
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        data = b'attachment-bytes'

    class FakeMessage:
        def __init__(self, path):
            self.path = path
            self.subject = 'MSG Update'
            self.sender = 'sender@example.com'
            self.to = 'recipient@example.com; second@example.com'
            self.cc = 'team@example.com'
            self.bcc = ''
            self.date = 'Wed, 12 Mar 2026 10:30:00 +0000'
            self.body = 'Plain message body.'
            self.htmlBody = '<html><body><p>HTML message body.</p></body></html>'
            self.attachments = [FakeAttachment()]
            self.headerDict = {
                'Reply-To': 'reply@example.com',
                'Message-ID': '<msg-1@example.com>',
            }

    monkeypatch.setattr(
        email_convert_module,
        'extract_msg',
        SimpleNamespace(Message=FakeMessage),
    )

    converter = EmailConverter(str(input_file), str(tmp_path), 'msg', 'json')
    [output_file] = converter.convert()
    payload = json.loads(Path(output_file).read_text(encoding='utf-8'))

    assert payload['subject'] == 'MSG Update'
    assert payload['to'] == ['recipient@example.com', 'second@example.com']
    assert payload['reply_to'] == ['reply@example.com']
    assert payload['message_id'] == '<msg-1@example.com>'
    assert payload['attachments'][0]['filename'] == 'report.xlsx'
    assert payload['attachments'][0]['size_bytes'] == len(b'attachment-bytes')