import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'PLDHE — Punjab Livestock Digital Health Ecosystem',
  description: 'Saraiki-first AI veterinary helpline for rural Punjab. Live call, instant triage, autonomous dispatch.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ur">
      <body>{children}</body>
    </html>
  );
}
