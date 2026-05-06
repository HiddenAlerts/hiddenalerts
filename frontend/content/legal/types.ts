/** Structured blocks for legal pages — edit copy in the content/*.ts files only. */

export type LegalBlock =
  | { type: 'paragraph'; text: string }
  | { type: 'sectionTitle'; text: string }
  | { type: 'bulletList'; items: string[] };

export type LegalPageDocument = {
  title: string;
  lastUpdated: string;
  blocks: LegalBlock[];
};
