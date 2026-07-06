import React from 'react';

interface WeaveLogoProps {
  gradientId?: string;
  className?: string;
}

const WeaveLogo: React.FC<WeaveLogoProps> = ({ gradientId = 'weave-grad', className = '' }) => (
  <div className={`flex items-center justify-center shrink-0 [&_svg]:w-full [&_svg]:h-full [&_svg]:object-contain ${className}`} aria-hidden>
    <svg viewBox="2 2 44 44" fill="none" xmlns="http://www.w3.org/2000/svg" className="text-white">
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#8b5cf6" />
          <stop offset="50%" stopColor="#d946ef" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>
      </defs>
      <g transform="translate(0,48) scale(1,-1)">
        <path d="M8 36 L14 12 L20 28 L26 12 L32 36" stroke={`url(#${gradientId})`} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        <path d="M11 36 L17 16 L23 32 L29 16 L37 36" stroke={`url(#${gradientId})`} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" opacity="0.8" />
        <path d="M14 36 L20 20 L26 36" stroke={`url(#${gradientId})`} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" opacity="0.6" />
      </g>
    </svg>
  </div>
);

export default WeaveLogo;
