import { Shield, CloudOff, Award } from 'lucide-react';

/**
 * Objection-handling strip. Three highest-friction concerns for a utility /
 * IPP procurement conversation, addressed inline so a scanner reads them in
 * two seconds:
 *   - "Is my SCADA data safe?"           → 256-bit encryption
 *   - "Do I have to integrate anything?" → zero SCADA integration
 *   - "Are you compliant?"                → ISO 27001 architecture
 */

const trustItems = [
  {
    icon: Shield,
    label: 'Bank-Level 256-bit Encryption',
    sub: 'AES-256 at rest, TLS 1.3 in transit',
  },
  {
    icon: CloudOff,
    label: 'Zero SCADA Integration Needed',
    sub: 'CSV upload — no on-prem agent',
  },
  {
    icon: Award,
    label: 'ISO 27001 Compliant Architecture',
    sub: 'Tamper-evident hash-chained audit log',
  },
];

export default function TrustBanner() {
  return (
    <section
      className="
        relative border-y border-canvas-hairline bg-canvas-raised
        ps-6 pe-6 py-6
      "
      aria-label="Security and trust indicators"
    >
      <div
        className="
          max-w-6xl mx-auto
          flex flex-wrap justify-center items-start
          gap-x-10 gap-y-6 md:gap-x-16
        "
      >
        {trustItems.map(({ icon: Icon, label, sub }) => (
          <div key={label} className="flex items-start gap-3 min-w-0">
            <div
              className="
                flex-shrink-0 mt-0.5
                w-9 h-9 rounded-lg
                bg-brand-cyan/10 border border-brand-cyan/25
                flex items-center justify-center
              "
            >
              <Icon
                className="w-4 h-4 text-brand-cyan"
                strokeWidth={1.75}
                aria-hidden="true"
              />
            </div>
            <div className="min-w-0">
              <div className="text-sm text-white font-medium leading-tight">
                {label}
              </div>
              <div className="text-xs text-white/50 mt-0.5">{sub}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
