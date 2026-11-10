export function Mark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="lg-a" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#3a5fe6" /><stop offset="1" stopColor="#1a2f8f" /></linearGradient>
        <linearGradient id="lg-b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#f6d27a" /><stop offset="1" stopColor="#c58f22" /></linearGradient>
      </defs>
      <rect width="100" height="100" rx="24" fill="url(#lg-a)" />
      <circle cx="43" cy="42" r="19" fill="none" stroke="#fff" strokeWidth="7.5" />
      <path d="M55.5 60.5 L62 54 L82 80 Z" fill="url(#lg-b)" />
    </svg>
  );
}

// العلامة النصية: «سومر» بخط كوفي (يستحضر النقوش الأولى) مع إسفين ذهبي — إشارة للخط المسماري، أول كتابة في التاريخ
export function Wordmark({ name = "سومر", className = "" }: { name?: string; className?: string }) {
  return (
    <div className={`relative inline-flex flex-col items-center ${className}`}>
      <span className="font-display text-7xl font-bold leading-none tracking-tight text-ink dark:text-white sm:text-8xl">{name}</span>
      <svg viewBox="0 0 64 14" className="mt-4 h-3.5 w-16" aria-hidden="true">
        <defs><linearGradient id="wm-g" x1="0" x2="1"><stop offset="0" stopColor="#f6d27a" /><stop offset="1" stopColor="#c58f22" /></linearGradient></defs>
        <path d="M0 7 L64 0 L64 14 Z" fill="url(#wm-g)" />
      </svg>
    </div>
  );
}
