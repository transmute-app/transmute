import base64
import json
import os
from dataclasses import asdict, dataclass
from email import policy
from email.message import Message
from email.parser import BytesParser
from email.utils import getaddresses
from html import escape
from pathlib import Path
from typing import Optional

import lxml.html
import pypandoc
from weasyprint import HTML

try:
    import extract_msg
except ImportError:
    extract_msg = None

from .converter_interface import ConverterInterface


@dataclass
class EmailAttachment:
    attachment_id: str
    filename: str
    content_type: str
    size_bytes: int
    content_disposition: str
    content_id: str
    is_inline: bool


@dataclass
class ParsedEmail:
    subject: str
    sender: str
    to: list[str]
    cc: list[str]
    bcc: list[str]
    reply_to: list[str]
    date: str
    message_id: str
    headers: dict[str, str]
    plain_body: str
    html_body: str
    text_body: str
    attachments: list[EmailAttachment]


class EmailConverter(ConverterInterface):
    supported_input_formats: set = {
        'eml',
        'msg',
    }
    supported_output_formats: set = {
        'txt',
        'md',
        'html',
        'pdf',
        'json',
        'docx',
        'odt',
        'epub',
        'rst',
        'rtf',
    }

    _pandoc_output_formats = {
        'docx',
        'odt',
        'epub',
        'rst',
        'rtf',
    }

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        super().__init__(input_file, output_dir, input_type, output_type)
        self._attachment_payloads: dict[str, bytes] = {}
        self._attachment_cid_map: dict[str, str] = {}

    def can_convert(self) -> bool:
        input_fmt = self.input_type.lower()
        output_fmt = self.output_type.lower()

        if input_fmt not in self.supported_input_formats:
            return False
        if output_fmt not in self.supported_output_formats:
            return False
        if input_fmt == output_fmt:
            return False

        return True

    @classmethod
    def get_formats_compatible_with(cls, format_type: str) -> set:
        fmt = format_type.lower()
        if fmt not in cls.supported_input_formats:
            return set()
        if fmt == 'msg' and extract_msg is None:
            return set()
        return cls.supported_output_formats - {fmt}

    @staticmethod
    def _read_message(input_file: str) -> Message:
        with open(input_file, 'rb') as file_handle:
            return BytesParser(policy=policy.default).parse(file_handle)

    @staticmethod
    def _get_header_values(message: Message, header_name: str) -> list[str]:
        return [address for _, address in getaddresses(message.get_all(header_name, [])) if address]

    @staticmethod
    def _get_text_content(part: Message) -> str:
        payload = part.get_content()
        if isinstance(payload, str):
            return payload.strip()
        if isinstance(payload, bytes):
            charset = part.get_content_charset() or 'utf-8'
            return payload.decode(charset, errors='replace').strip()
        return ''

    @staticmethod
    def _html_to_text(html_content: str) -> str:
        if not html_content.strip():
            return ''

        root = lxml.html.fromstring(html_content)
        lines = [line.strip() for line in root.text_content().splitlines()]
        return '\n'.join(line for line in lines if line)

    @staticmethod
    def _sanitize_html_fragment(html_content: str) -> str:
        if not html_content.strip():
            return ''

        root = lxml.html.fragment_fromstring(html_content, create_parent='div')
        for node in root.xpath('.//script|.//iframe|.//object|.//embed|.//link|.//meta|.//audio|.//video|.//source'):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)

        return lxml.html.tostring(root, encoding='unicode', method='html')

    @staticmethod
    def _normalize_content_id(content_id: str | None) -> str:
        if not content_id:
            return ''
        normalized = str(content_id).strip().removeprefix('cid:')
        if normalized.startswith('<') and normalized.endswith('>'):
            normalized = normalized[1:-1]
        return normalized.strip()

    @staticmethod
    def _coerce_payload_bytes(payload) -> bytes:
        if payload is None:
            return b''
        if isinstance(payload, bytes):
            return payload
        if isinstance(payload, str):
            return payload.encode('utf-8')
        try:
            return bytes(payload)
        except Exception:
            return b''

    def _register_attachment_payload(self, payload: bytes, content_id: str = '') -> str:
        attachment_id = f'attachment-{len(self._attachment_payloads) + 1}'
        self._attachment_payloads[attachment_id] = payload
        normalized_content_id = self._normalize_content_id(content_id)
        if normalized_content_id:
            self._attachment_cid_map[normalized_content_id] = attachment_id
        return attachment_id

    @staticmethod
    def _payload_to_data_uri(content_type: str, payload: bytes) -> str:
        encoded = base64.b64encode(payload).decode('ascii')
        return f'data:{content_type};base64,{encoded}'

    def _resolve_cid_references(self, html_content: str) -> str:
        if not html_content.strip():
            return ''

        root = lxml.html.fragment_fromstring(html_content, create_parent='div')
        for node in root.xpath('.//*[@src or @href or @background or @poster]'):
            for attribute_name in ('src', 'href', 'background', 'poster'):
                raw_value = node.get(attribute_name)
                if not raw_value or not raw_value.startswith('cid:'):
                    continue

                attachment_id = self._attachment_cid_map.get(
                    self._normalize_content_id(raw_value)
                )
                payload = self._attachment_payloads.get(attachment_id or '')
                if not attachment_id or payload is None:
                    continue

                content_type = 'application/octet-stream'
                for attachment in getattr(self, '_parsed_attachments', []):
                    if attachment.attachment_id == attachment_id:
                        content_type = attachment.content_type
                        break

                node.set(attribute_name, self._payload_to_data_uri(content_type, payload))

        return lxml.html.tostring(root, encoding='unicode', method='html')

    @staticmethod
    def _normalize_address_list(value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [entry.strip() for entry in value if entry and entry.strip()]

        normalized = value.replace(';', ',')
        return [address for _, address in getaddresses([normalized]) if address]

    @staticmethod
    def _coerce_attachment_size_bytes(attachment) -> int:
        data = getattr(attachment, 'data', None)
        if data is None:
            return 0
        if isinstance(data, bytes):
            return len(data)
        if isinstance(data, str):
            return len(data.encode('utf-8'))
        try:
            return len(data)
        except TypeError:
            return 0

    @staticmethod
    def _coerce_msg_header_dict(message) -> dict[str, str]:
        header_dict = getattr(message, 'headerDict', None) or {}
        normalized_headers: dict[str, str] = {}
        for key, value in header_dict.items():
            normalized_headers[str(key)] = str(value)
        return normalized_headers

    @staticmethod
    def _render_text_attachment_preview(payload: bytes) -> str:
        text = payload.decode('utf-8', errors='replace').strip()
        if len(text) > 4000:
            text = text[:4000].rstrip() + '\n\n[Preview truncated]'
        return '<details><summary>Preview</summary><pre>' + escape(text or '[Empty attachment]') + '</pre></details>'

    def _build_attachment_html(self, attachments: list[EmailAttachment]) -> str:
        if not attachments:
            return ''

        items: list[str] = []
        for attachment in attachments:
            payload = self._attachment_payloads.get(attachment.attachment_id, b'')
            download_href = self._payload_to_data_uri(attachment.content_type, payload) if payload else ''
            preview_html = ''

            if payload and attachment.content_type.startswith('image/'):
                preview_html = (
                    '<div class="attachment-preview attachment-image">'
                    f'<img src="{download_href}" alt="{escape(attachment.filename)}">'
                    '</div>'
                )
            elif payload and (
                attachment.content_type.startswith('text/')
                or attachment.content_type in {'application/json', 'application/xml'}
                or attachment.filename.lower().endswith(('.txt', '.json', '.xml', '.csv', '.md'))
            ):
                preview_html = self._render_text_attachment_preview(payload)

            download_link = ''
            if download_href:
                download_link = (
                    f'<a href="{download_href}" download="{escape(attachment.filename)}">'
                    'Download inline copy</a>'
                )

            items.append(
                '<li class="attachment-item">'
                f'<div><strong>{escape(attachment.filename)}</strong> '
                f'<span>({escape(attachment.content_type)}, {attachment.size_bytes} bytes)</span></div>'
                f'{download_link}'
                f'{preview_html}'
                '</li>'
            )

        return '<section><h2>Attachments</h2><ul class="attachments">' + ''.join(items) + '</ul></section>'

    def _parse_msg(self) -> ParsedEmail:
        if extract_msg is None:
            raise RuntimeError(
                'MSG conversion requires extract-msg to be installed.'
            )

        message = extract_msg.Message(self.input_file)
        attachments: list[EmailAttachment] = []
        for attachment in getattr(message, 'attachments', []) or []:
            payload = self._coerce_payload_bytes(getattr(attachment, 'data', None))
            filename = (
                getattr(attachment, 'longFilename', None)
                or getattr(attachment, 'name', None)
                or getattr(attachment, 'shortFilename', None)
                or 'attachment'
            )
            content_id = self._normalize_content_id(
                getattr(attachment, 'contentId', None) or getattr(attachment, 'contentID', None)
            )
            attachments.append(
                EmailAttachment(
                    attachment_id=self._register_attachment_payload(payload, content_id),
                    filename=str(filename),
                    content_type=str(getattr(attachment, 'mimetype', None) or 'application/octet-stream'),
                    size_bytes=len(payload) or self._coerce_attachment_size_bytes(attachment),
                    content_disposition='attachment',
                    content_id=content_id,
                    is_inline=bool(content_id),
                )
            )

        header_dict = self._coerce_msg_header_dict(message)
        reply_to = self._normalize_address_list(
            header_dict.get('Reply-To') or header_dict.get('reply-to')
        )
        message_id = str(
            header_dict.get('Message-ID')
            or header_dict.get('Message-Id')
            or header_dict.get('message-id')
            or ''
        )
        html_body = self._sanitize_html_fragment(str(getattr(message, 'htmlBody', '') or ''))
        plain_body = str(getattr(message, 'body', '') or '').strip()
        text_body = plain_body or self._html_to_text(html_body)

        return ParsedEmail(
            subject=str(getattr(message, 'subject', '') or 'Untitled Email'),
            sender=str(getattr(message, 'sender', '') or ''),
            to=self._normalize_address_list(getattr(message, 'to', None)),
            cc=self._normalize_address_list(getattr(message, 'cc', None)),
            bcc=self._normalize_address_list(getattr(message, 'bcc', None)),
            reply_to=reply_to,
            date=str(getattr(message, 'date', '') or ''),
            message_id=message_id,
            headers=header_dict,
            plain_body=plain_body,
            html_body=html_body,
            text_body=text_body,
            attachments=attachments,
        )

    def _parse_email(self) -> ParsedEmail:
        if self.input_type.lower() == 'msg':
            parsed_email = self._parse_msg()
            self._parsed_attachments = parsed_email.attachments
            return parsed_email

        message = self._read_message(self.input_file)

        plain_parts: list[str] = []
        html_parts: list[str] = []
        attachments: list[EmailAttachment] = []

        for part in message.walk():
            if part.is_multipart():
                continue

            filename = part.get_filename() or ''
            disposition = part.get_content_disposition() or 'inline'
            content_type = part.get_content_type()
            content_id = self._normalize_content_id(part.get('Content-ID'))

            if disposition == 'attachment' or filename:
                payload = part.get_payload(decode=True) or b''
                attachments.append(
                    EmailAttachment(
                        attachment_id=self._register_attachment_payload(payload, content_id),
                        filename=filename or 'attachment',
                        content_type=content_type,
                        size_bytes=len(payload),
                        content_disposition=disposition,
                        content_id=content_id,
                        is_inline=disposition == 'inline' or bool(content_id),
                    )
                )
                continue

            text_content = self._get_text_content(part)
            if not text_content:
                continue

            if content_type == 'text/plain':
                plain_parts.append(text_content)
            elif content_type == 'text/html':
                html_parts.append(text_content)

        plain_body = '\n\n'.join(part for part in plain_parts if part).strip()
        html_body = '\n'.join(part for part in html_parts if part).strip()
        sanitized_html_body = self._sanitize_html_fragment(html_body)
        text_body = plain_body or self._html_to_text(sanitized_html_body)

        headers = {key: str(value) for key, value in message.items()}
        parsed_email = ParsedEmail(
            subject=str(message.get('subject', 'Untitled Email')),
            sender=str(message.get('from', '')),
            to=self._get_header_values(message, 'to'),
            cc=self._get_header_values(message, 'cc'),
            bcc=self._get_header_values(message, 'bcc'),
            reply_to=self._get_header_values(message, 'reply-to'),
            date=str(message.get('date', '')),
            message_id=str(message.get('message-id', '')),
            headers=headers,
            plain_body=plain_body,
            html_body=sanitized_html_body,
            text_body=text_body,
            attachments=attachments,
        )
        self._parsed_attachments = parsed_email.attachments
        return parsed_email

    @staticmethod
    def _format_people(values: list[str]) -> str:
        return ', '.join(values)

    def _build_text_output(self, parsed_email: ParsedEmail) -> str:
        header_lines = [
            f"Subject: {parsed_email.subject}",
            f"From: {parsed_email.sender}",
        ]
        if parsed_email.to:
            header_lines.append(f"To: {self._format_people(parsed_email.to)}")
        if parsed_email.cc:
            header_lines.append(f"Cc: {self._format_people(parsed_email.cc)}")
        if parsed_email.reply_to:
            header_lines.append(f"Reply-To: {self._format_people(parsed_email.reply_to)}")
        if parsed_email.date:
            header_lines.append(f"Date: {parsed_email.date}")
        if parsed_email.message_id:
            header_lines.append(f"Message-ID: {parsed_email.message_id}")

        body = parsed_email.text_body or '[No body content]'
        content = '\n'.join(header_lines) + f"\n\n{body}"

        if parsed_email.attachments:
            attachment_lines = [
                f"- {attachment.filename} ({attachment.content_type}, {attachment.size_bytes} bytes)"
                for attachment in parsed_email.attachments
            ]
            content += '\n\nAttachments:\n' + '\n'.join(attachment_lines)

        return content

    def _build_markdown_output(self, parsed_email: ParsedEmail) -> str:
        body_markdown = parsed_email.text_body or ''
        if parsed_email.html_body:
            try:
                body_markdown = pypandoc.convert_text(parsed_email.html_body, 'gfm', format='html').strip()
            except Exception:
                body_markdown = parsed_email.text_body or ''

        lines = [f"# {parsed_email.subject}", '']
        if parsed_email.sender:
            lines.append(f"- From: {parsed_email.sender}")
        if parsed_email.to:
            lines.append(f"- To: {self._format_people(parsed_email.to)}")
        if parsed_email.cc:
            lines.append(f"- Cc: {self._format_people(parsed_email.cc)}")
        if parsed_email.reply_to:
            lines.append(f"- Reply-To: {self._format_people(parsed_email.reply_to)}")
        if parsed_email.date:
            lines.append(f"- Date: {parsed_email.date}")
        if parsed_email.message_id:
            lines.append(f"- Message-ID: {parsed_email.message_id}")

        lines.extend(['', '## Body', '', body_markdown or '_No body content_'])

        if parsed_email.attachments:
            lines.extend(['', '## Attachments', ''])
            for attachment in parsed_email.attachments:
                lines.append(
                    f"- {attachment.filename} ({attachment.content_type}, {attachment.size_bytes} bytes)"
                )

        return '\n'.join(lines).strip() + '\n'

    def _build_html_output(self, parsed_email: ParsedEmail) -> str:
        attachment_html = self._build_attachment_html(parsed_email.attachments)

        metadata_rows = []
        for label, value in [
            ('From', parsed_email.sender),
            ('To', self._format_people(parsed_email.to)),
            ('Cc', self._format_people(parsed_email.cc)),
            ('Reply-To', self._format_people(parsed_email.reply_to)),
            ('Date', parsed_email.date),
            ('Message-ID', parsed_email.message_id),
        ]:
            if value:
                metadata_rows.append(
                    f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>"
                )

        body_html = self._resolve_cid_references(parsed_email.html_body)
        if not body_html:
            body_html = '<pre>' + escape(parsed_email.text_body or '[No body content]') + '</pre>'

        return (
            '<!DOCTYPE html>'
            '<html>'
            '<head>'
            '<meta charset="utf-8">'
            f'<title>{escape(parsed_email.subject)}</title>'
            '<style>'
            'body { font-family: sans-serif; margin: 2rem; color: #1f2937; line-height: 1.6; }'
            'h1, h2 { color: #111827; }'
            'dl { display: grid; grid-template-columns: max-content 1fr; gap: 0.5rem 1rem; }'
            'dt { font-weight: 700; }'
            'dd { margin: 0; }'
            'pre { white-space: pre-wrap; background: #f9fafb; padding: 1rem; border-radius: 0.5rem; }'
            'section { margin-top: 2rem; }'
            '.attachments { list-style: none; padding: 0; display: grid; gap: 1rem; }'
            '.attachment-item { border: 1px solid #d1d5db; border-radius: 0.75rem; padding: 1rem; background: #ffffff; }'
            '.attachment-item a { display: inline-block; margin-top: 0.5rem; }'
            '.attachment-preview { margin-top: 0.75rem; }'
            '.attachment-image img { max-width: 100%; height: auto; border-radius: 0.5rem; border: 1px solid #e5e7eb; }'
            '</style>'
            '</head>'
            '<body>'
            f'<h1>{escape(parsed_email.subject)}</h1>'
            f'<section><dl>{"".join(metadata_rows)}</dl></section>'
            f'<section><h2>Body</h2>{body_html}</section>'
            f'{attachment_html}'
            '</body>'
            '</html>'
        )

    @staticmethod
    def _build_json_output(parsed_email: ParsedEmail) -> str:
        payload = asdict(parsed_email)
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def _convert_with_pandoc(self, html_content: str, output_file: str) -> None:
        try:
            pypandoc.convert_text(
                html_content,
                self.output_type.lower(),
                format='html',
                outputfile=output_file,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Email conversion to {self.output_type} requires pandoc and failed: {str(exc)}"
            )

    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        if not self.can_convert():
            raise ValueError(
                f"Conversion from {self.input_type} to {self.output_type} is not supported."
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        input_filename = Path(self.input_file).stem
        output_file = os.path.join(
            self.output_dir, f"{input_filename}.{self.output_type}"
        )

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        parsed_email = self._parse_email()
        html_content = self._build_html_output(parsed_email)

        try:
            if self.output_type == 'txt':
                content = self._build_text_output(parsed_email)
                with open(output_file, 'w', encoding='utf-8') as file_handle:
                    file_handle.write(content)
            elif self.output_type == 'md':
                content = self._build_markdown_output(parsed_email)
                with open(output_file, 'w', encoding='utf-8') as file_handle:
                    file_handle.write(content)
            elif self.output_type == 'html':
                with open(output_file, 'w', encoding='utf-8') as file_handle:
                    file_handle.write(html_content)
            elif self.output_type == 'json':
                with open(output_file, 'w', encoding='utf-8') as file_handle:
                    file_handle.write(self._build_json_output(parsed_email))
            elif self.output_type == 'pdf':
                HTML(string=html_content).write_pdf(output_file)
            elif self.output_type in self._pandoc_output_formats:
                self._convert_with_pandoc(html_content, output_file)
            else:
                raise ValueError(f"Unsupported output format: {self.output_type}")

            if not os.path.exists(output_file):
                raise RuntimeError(f"Output file was not created: {output_file}")

            return [output_file]
        except (ValueError, RuntimeError):
            raise
        except Exception as exc:
            raise RuntimeError(f"Email conversion failed: {str(exc)}")