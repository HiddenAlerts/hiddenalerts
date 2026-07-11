import { cn } from '@/lib/utils';

/**
 * Shared Tailwind classes for rendering Tiptap-produced HTML — headings,
 * lists, quotes, links. Used by both the live editor (`RichTextEditor`) and
 * every read-only renderer (`BriefReader`) so formatting like h1/h2/bullets
 * looks identical everywhere the same HTML is shown, not just in the editor.
 */
export const TIPTAP_CONTENT_CLASSNAME = cn(
  '[&_p]:my-2',
  '[&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5',
  '[&_blockquote]:border-border [&_blockquote]:text-muted [&_blockquote]:border-l-2 [&_blockquote]:pl-3',
  '[&_a]:text-primary-400 [&_a]:underline',
  '[&_h1]:text-foreground [&_h1]:mt-3 [&_h1]:mb-1.5 [&_h1]:text-2xl [&_h1]:font-semibold',
  '[&_h2]:text-foreground [&_h2]:mt-3 [&_h2]:mb-1.5 [&_h2]:text-xl [&_h2]:font-semibold',
  '[&_h3]:text-foreground [&_h3]:mt-2.5 [&_h3]:mb-1 [&_h3]:text-lg [&_h3]:font-semibold',
  '[&_h4]:text-foreground [&_h4]:mt-2 [&_h4]:mb-1 [&_h4]:text-base [&_h4]:font-semibold',
  '[&_h5]:text-foreground [&_h5]:mt-2 [&_h5]:mb-1 [&_h5]:text-sm [&_h5]:font-semibold',
  '[&_h6]:text-foreground [&_h6]:mt-2 [&_h6]:mb-1 [&_h6]:text-xs [&_h6]:font-semibold [&_h6]:tracking-wide [&_h6]:uppercase',
);
