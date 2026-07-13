export type SourceIconVariant =
  | 'seal'
  | 'shield'
  | 'network'
  | 'bank'
  | 'scales'
  | 'cyber'
  | 'press'
  | 'tech';

export type MonitorSource = {
  id: string;
  acronym: string;
  fullName?: string;
  icon: SourceIconVariant;
};

export const SOURCES_WE_MONITOR = {
  title: 'Sources We Monitor',
  sources: [
    {
      id: 'fbi',
      acronym: 'FBI',
      fullName: 'Federal Bureau of Investigation',
      icon: 'seal',
    },
    {
      id: 'ic3',
      acronym: 'IC3',
      fullName: 'Internet Crime Complaint Center',
      icon: 'network',
    },
    {
      id: 'doj',
      acronym: 'DOJ',
      fullName: 'Department of Justice',
      icon: 'seal',
    },
    {
      id: 'ftc',
      acronym: 'FTC',
      fullName: 'Federal Trade Commission',
      icon: 'shield',
    },
    {
      id: 'fincen',
      acronym: 'FinCEN',
      fullName: 'Financial Crimes Enforcement Network',
      icon: 'bank',
    },
    {
      id: 'sec',
      acronym: 'SEC',
      fullName: 'U.S. Securities and Exchange Commission',
      icon: 'scales',
    },
    {
      id: 'cisa',
      acronym: 'CISA',
      fullName: 'Cybersecurity & Infrastructure Security Agency',
      icon: 'cyber',
    },
    {
      id: 'krebs',
      acronym: 'KrebsOnSecurity',
      fullName: 'Industry security reporting',
      icon: 'press',
    },
    {
      id: 'bleeping',
      acronym: 'BleepingComputer',
      fullName: 'Cybersecurity news & analysis',
      icon: 'tech',
    },
  ] as ReadonlyArray<MonitorSource>,
  footnote:
    '10+ government, regulatory, law enforcement, and industry sources. Updated multiple times daily.',
} as const;
