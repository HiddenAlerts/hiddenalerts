export type SourceVariant = 'seal' | 'shield' | 'text' | 'brand';

export type MonitorSource = {
  id: string;
  acronym: string;
  fullName?: string;
  variant: SourceVariant;
};

export const SOURCES_WE_MONITOR = {
  title: 'Sources We Monitor',
  sources: [
    {
      id: 'fbi',
      acronym: 'FBI',
      variant: 'seal',
    },
    {
      id: 'ic3',
      acronym: 'IC3',
      fullName: 'Internet Crime Complaint Center',
      variant: 'text',
    },
    {
      id: 'doj',
      acronym: 'DOJ',
      fullName: 'Department of Justice',
      variant: 'seal',
    },
    {
      id: 'ftc',
      acronym: 'FTC',
      fullName: 'Federal Trade Commission',
      variant: 'shield',
    },
    {
      id: 'fincen',
      acronym: 'FinCEN',
      fullName: 'Financial Crimes Enforcement Network',
      variant: 'text',
    },
    {
      id: 'sec',
      acronym: 'SEC',
      fullName: 'U.S. Securities and Exchange Commission',
      variant: 'text',
    },
    {
      id: 'cisa',
      acronym: 'CISA',
      fullName: 'Cybersecurity & Infrastructure Security Agency',
      variant: 'text',
    },
    {
      id: 'krebs',
      acronym: 'KrebsOnSecurity',
      variant: 'brand',
    },
    {
      id: 'bleeping',
      acronym: 'BleepingComputer',
      variant: 'brand',
    },
  ] as ReadonlyArray<MonitorSource>,
  footnote:
    '10+ government, regulatory, law enforcement, and industry sources. Updated multiple times daily.',
} as const;
