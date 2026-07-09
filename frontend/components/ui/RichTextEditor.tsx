'use client';

import { TIPTAP_CONTENT_CLASSNAME } from '@/lib/tiptapContentStyles';
import { cn } from '@/lib/utils';
import CharacterCount from '@tiptap/extension-character-count';
import Placeholder from '@tiptap/extension-placeholder';
import { EditorContent, type Editor, useEditor } from '@tiptap/react';
import { BubbleMenu } from '@tiptap/react/menus';
import StarterKit from '@tiptap/starter-kit';
import {
  Bold,
  ExternalLink,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
  Pencil,
  Quote,
  Underline as UnderlineIcon,
  Unlink,
} from 'lucide-react';
import * as React from 'react';

import { labelSize } from './input';

const HEADING_LEVELS = [1, 2, 3, 4, 5, 6] as const;

const TEXT_STYLE_OPTIONS = [
  { value: 'paragraph', label: 'Paragraph' },
  { value: '1', label: 'Heading 1' },
  { value: '2', label: 'Heading 2' },
  { value: '3', label: 'Heading 3' },
  { value: '4', label: 'Heading 4' },
  { value: '5', label: 'Heading 5' },
  { value: '6', label: 'Heading 6' },
];

export type RichTextEditorProps = {
  label?: string;
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  id?: string;
  required?: boolean;
  addAsterisk?: boolean;
  isError?: boolean;
  errorMessage?: string;
  parentStyles?: string;
  disabled?: boolean;
  /** Show a live word count under the editor (e.g. the main brief). */
  showWordCount?: boolean;
  minHeightClassName?: string;
};

function ToolbarButton({
  onClick,
  active,
  disabled,
  label,
  children,
}: {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onMouseDown={e => e.preventDefault()}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      aria-pressed={active}
      className={cn(
        'text-muted hover:bg-surface-muted hover:text-foreground inline-flex size-7 items-center justify-center rounded transition-colors disabled:pointer-events-none disabled:opacity-40',
        active && 'bg-surface-muted text-foreground',
      )}
    >
      {children}
    </button>
  );
}

function TextStyleSelect({ editor }: { editor: Editor }) {
  const activeLevel = HEADING_LEVELS.find(level =>
    editor.isActive('heading', { level }),
  );
  const value = activeLevel ? String(activeLevel) : 'paragraph';

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = e.target.value;
    if (next === 'paragraph') {
      editor.chain().focus().setParagraph().run();
    } else {
      editor
        .chain()
        .focus()
        .setHeading({ level: Number(next) as (typeof HEADING_LEVELS)[number] })
        .run();
    }
  }

  return (
    <select
      aria-label="Text style"
      value={value}
      onChange={handleChange}
      className="text-muted hover:text-foreground bg-surface-muted/60 h-7 cursor-pointer rounded border-none px-1.5 text-xs transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-primary-500/50"
    >
      {TEXT_STYLE_OPTIONS.map(opt => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

function Toolbar({ editor }: { editor: Editor | null }) {
  if (!editor) return null;

  const setLink = () => {
    const previousUrl = editor.getAttributes('link').href as
      | string
      | undefined;
    const url = window.prompt('Enter URL', previousUrl ?? '');
    if (url === null) return;
    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
  };

  return (
    <div className="border-border bg-surface-muted/40 flex flex-wrap items-center gap-0.5 rounded-t-md border-b px-2 py-1.5">
      <TextStyleSelect editor={editor} />
      <span className="bg-border mx-1 h-5 w-px" aria-hidden />
      <ToolbarButton
        label="Bold"
        active={editor.isActive('bold')}
        onClick={() => editor.chain().focus().toggleBold().run()}
      >
        <Bold className="size-4" aria-hidden />
      </ToolbarButton>
      <ToolbarButton
        label="Italic"
        active={editor.isActive('italic')}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      >
        <Italic className="size-4" aria-hidden />
      </ToolbarButton>
      <ToolbarButton
        label="Underline"
        active={editor.isActive('underline')}
        onClick={() => editor.chain().focus().toggleUnderline().run()}
      >
        <UnderlineIcon className="size-4" aria-hidden />
      </ToolbarButton>
      <span className="bg-border mx-1 h-5 w-px" aria-hidden />
      <ToolbarButton
        label="Bullet list"
        active={editor.isActive('bulletList')}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      >
        <List className="size-4" aria-hidden />
      </ToolbarButton>
      <ToolbarButton
        label="Numbered list"
        active={editor.isActive('orderedList')}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      >
        <ListOrdered className="size-4" aria-hidden />
      </ToolbarButton>
      <ToolbarButton
        label="Quote"
        active={editor.isActive('blockquote')}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
      >
        <Quote className="size-4" aria-hidden />
      </ToolbarButton>
      <span className="bg-border mx-1 h-5 w-px" aria-hidden />
      <ToolbarButton label="Add link" active={editor.isActive('link')} onClick={setLink}>
        <LinkIcon className="size-4" aria-hidden />
      </ToolbarButton>
      <ToolbarButton
        label="Remove link"
        disabled={!editor.isActive('link')}
        onClick={() => editor.chain().focus().unsetLink().run()}
      >
        <Unlink className="size-4" aria-hidden />
      </ToolbarButton>
    </div>
  );
}

const bubbleButtonClass =
  'text-muted hover:bg-surface-muted hover:text-foreground inline-flex size-7 items-center justify-center rounded transition-colors';

/**
 * Floating menu shown when the cursor is inside a link: preview (open in a
 * new tab), edit the URL inline, or remove the link.
 */
function LinkBubbleMenu({ editor, pluginKey }: { editor: Editor; pluginKey: string }) {
  const [isEditing, setIsEditing] = React.useState(false);
  const [draftUrl, setDraftUrl] = React.useState('');
  const inputRef = React.useRef<HTMLInputElement>(null);

  function openLink() {
    const href = editor.getAttributes('link').href as string | undefined;
    if (href) window.open(href, '_blank', 'noopener,noreferrer');
  }

  function startEditing() {
    setDraftUrl((editor.getAttributes('link').href as string | undefined) ?? '');
    setIsEditing(true);
    requestAnimationFrame(() => inputRef.current?.focus());
  }

  function saveEditing() {
    const url = draftUrl.trim();
    if (url) {
      editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
    } else {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
    }
    setIsEditing(false);
  }

  function removeLink() {
    editor.chain().focus().extendMarkRange('link').unsetLink().run();
    setIsEditing(false);
  }

  return (
    <BubbleMenu
      editor={editor}
      pluginKey={pluginKey}
      shouldShow={({ editor }) => editor.isActive('link')}
      options={{ placement: 'bottom', offset: 8, onHide: () => setIsEditing(false) }}
      className="border-border bg-surface flex items-center gap-0.5 rounded-md border p-1 shadow-lg"
    >
      {isEditing ? (
        <form
          onSubmit={e => {
            e.preventDefault();
            saveEditing();
          }}
          className="flex items-center gap-1"
        >
          <input
            ref={inputRef}
            value={draftUrl}
            onChange={e => setDraftUrl(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Escape') setIsEditing(false);
            }}
            placeholder="https://…"
            className="text-body bg-transparent w-52 px-1.5 py-1 text-xs focus:outline-none"
          />
          <button
            type="submit"
            className="text-primary-400 hover:text-primary-300 px-1.5 text-xs font-semibold"
          >
            Save
          </button>
        </form>
      ) : (
        <>
          <button
            type="button"
            onClick={openLink}
            aria-label="Open link in new tab"
            className={bubbleButtonClass}
          >
            <ExternalLink className="size-3.5" aria-hidden />
          </button>
          <button
            type="button"
            onClick={startEditing}
            aria-label="Edit link"
            className={bubbleButtonClass}
          >
            <Pencil className="size-3.5" aria-hidden />
          </button>
          <button
            type="button"
            onClick={removeLink}
            aria-label="Remove link"
            className={cn(bubbleButtonClass, 'hover:text-danger')}
          >
            <Unlink className="size-3.5" aria-hidden />
          </button>
        </>
      )}
    </BubbleMenu>
  );
}

/**
 * Tiptap-based rich text field styled to match `Input`/`Textarea`. Stores
 * content as an HTML string via `onChange`.
 */
export function RichTextEditor({
  label,
  value,
  onChange,
  placeholder,
  id,
  required,
  addAsterisk,
  isError,
  errorMessage,
  parentStyles,
  disabled,
  showWordCount,
  minHeightClassName = 'min-h-[140px]',
}: RichTextEditorProps) {
  const uid = React.useId();
  const fieldId = id ?? `rte-${uid}`;
  const showAsterisk = Boolean(
    required && addAsterisk && label && !label.includes('*'),
  );

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        link: { openOnClick: false, autolink: true },
      }),
      Placeholder.configure({ placeholder }),
      CharacterCount,
    ],
    content: value,
    editable: !disabled,
    editorProps: {
      attributes: {
        id: fieldId,
        class: cn(
          'font-manrope text-body max-w-none px-3 py-2.5 text-sm focus:outline-none',
          '[&_p]:my-1 [&_p.is-editor-empty:first-child::before]:text-muted',
          "[&_p.is-editor-empty:first-child::before]:pointer-events-none [&_p.is-editor-empty:first-child::before]:float-left [&_p.is-editor-empty:first-child::before]:h-0 [&_p.is-editor-empty:first-child::before]:content-[attr(data-placeholder)]",
          TIPTAP_CONTENT_CLASSNAME,
          minHeightClassName,
        ),
      },
    },
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  });

  React.useEffect(() => {
    if (!editor) return;
    if (value !== editor.getHTML()) {
      editor.commands.setContent(value, { emitUpdate: false });
    }
  }, [value, editor]);

  React.useEffect(() => {
    editor?.setEditable(!disabled);
  }, [disabled, editor]);

  const wordCount = editor?.storage.characterCount?.words() ?? 0;

  return (
    <div
      className={cn(
        'flex flex-col gap-2',
        disabled && 'cursor-not-allowed',
        parentStyles,
      )}
    >
      {label ? (
        <label htmlFor={fieldId} className={labelSize.md}>
          {label}
          {showAsterisk ? (
            <span className="text-danger-500 ml-0.5 font-medium">*</span>
          ) : null}
        </label>
      ) : null}

      <div
        className={cn(
          'bg-surface overflow-hidden rounded-md border transition-colors',
          'focus-within:ring-2',
          isError
            ? 'border-danger focus-within:border-danger focus-within:ring-danger/25'
            : 'border-border focus-within:border-primary-500 focus-within:ring-primary-500/30',
          disabled && 'pointer-events-none opacity-40',
        )}
      >
        <Toolbar editor={editor} />
        <EditorContent editor={editor} />
        {editor ? (
          <LinkBubbleMenu editor={editor} pluginKey={`link-bubble-${fieldId}`} />
        ) : null}
        {showWordCount ? (
          <div className="border-border text-muted flex justify-end border-t px-3 py-1.5 text-xs">
            {wordCount} words
          </div>
        ) : null}
      </div>

      {isError && errorMessage ? (
        <p className="text-danger-400 text-xs">{errorMessage}</p>
      ) : null}
    </div>
  );
}
