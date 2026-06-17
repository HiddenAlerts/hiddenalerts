import type { LegalPageDocument } from '@/content/legal/types';
import type { FC } from 'react';

type LegalPageProps = {
  document: LegalPageDocument;
};

export const LegalPage: FC<LegalPageProps> = ({ document }) => {
  return (
    <main className="bg-background text-foreground min-h-full">
      <article className="text-body mx-auto max-w-[720px] px-4 py-12 sm:px-6">
        <header className="mb-10">
          <h1 className="text-foreground">{document.title}</h1>
          <p className="text-muted-foreground mt-3 text-sm">
            Last updated: {document.lastUpdated}
          </p>
        </header>
        <div className="flex flex-col gap-5 text-sm leading-relaxed sm:text-[15px] sm:leading-relaxed">
          {document.blocks.map((block, index) => {
            const key = `${block.type}-${index}`;
            switch (block.type) {
              case 'paragraph':
                return (
                  <p key={key} className="text-body">
                    {block.text}
                  </p>
                );
              case 'sectionTitle':
                return (
                  <h2
                    key={key}
                    className="text-foreground font-heading text-base font-semibold tracking-tight"
                  >
                    {block.text}
                  </h2>
                );
              case 'bulletList':
                return (
                  <ul
                    key={key}
                    className="text-body list-disc space-y-2 pl-5 marker:text-muted-foreground"
                  >
                    {block.items.map((item, itemIndex) => (
                      <li key={`${index}-${itemIndex}`}>{item}</li>
                    ))}
                  </ul>
                );
              default:
                return null;
            }
          })}
        </div>
      </article>
    </main>
  );
};
