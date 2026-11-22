import React from 'react';

type Ribbon = {
  id: string;
  cycles: number;
  amplitude: number;
  baseline: number;
  duration: string;
  delay: string;
  crest: string;
  mid: string;
  gloss: string;
  top: string;
  depth: string;
  opacity: number;
};

const RIBBONS: Ribbon[] = [
  {
    id: 'near',
    cycles: 2,
    amplitude: 16,
    baseline: 72,
    duration: '72s',
    delay: '0s',
    crest: '#ffffff',
    mid: '#c5e9f8',
    gloss: '#ffffff',
    top: '6%',
    depth: '40px',
    opacity: 0.92,
  },
  {
    id: 'mid',
    cycles: 2,
    amplitude: 20,
    baseline: 84,
    duration: '96s',
    delay: '-18s',
    crest: '#f4fbff',
    mid: '#9ecfee',
    gloss: '#ffffff',
    top: '18%',
    depth: '-30px',
    opacity: 0.78,
  },
  {
    id: 'far',
    cycles: 2,
    amplitude: 14,
    baseline: 80,
    duration: '120s',
    delay: '-30s',
    crest: '#f7f4ff',
    mid: '#e4dcff',
    gloss: '#ffffff',
    top: '32%',
    depth: '-110px',
    opacity: 0.62,
  },
  {
    id: 'horizon',
    cycles: 2,
    amplitude: 10,
    baseline: 68,
    duration: '140s',
    delay: '-40s',
    crest: '#f4fbff',
    mid: '#c5e8f8',
    gloss: '#ffffff',
    top: '46%',
    depth: '-190px',
    opacity: 0.5,
  },
];

function ribbonPaths(cycles: number, amplitude: number, baseline: number) {
  const width = 2000;
  const bottom = baseline + amplitude + 22;
  const steps = 280;
  const crest: string[] = [];
  for (let i = 0; i <= steps; i += 1) {
    const x = (i / steps) * width;
    const y = baseline + Math.sin((i / steps) * Math.PI * 2 * cycles) * amplitude;
    const cmd = i === 0 ? 'M' : 'L';
    crest.push(`${cmd} ${x.toFixed(1)} ${y.toFixed(1)}`);
  }
  const crestPath = crest.join(' ');
  return {
    fill: `${crestPath} L ${width} ${bottom} L 0 ${bottom} Z`,
    crest: crestPath,
  };
}

const LoginWaves: React.FC = () => (
  <div className="login-waves" aria-hidden="true">
    <div className="login-waves__glow login-waves__glow--left" />
    <div className="login-waves__glow login-waves__glow--right" />
    <div className="login-waves__horizon" />
    <div className="login-waves__stage">
      <div className="login-waves__floor">
        {RIBBONS.map((ribbon) => {
          const paths = ribbonPaths(ribbon.cycles, ribbon.amplitude, ribbon.baseline);
          const fillId = `login-wave-fill-${ribbon.id}`;
          const glossId = `login-wave-gloss-${ribbon.id}`;
          return (
            <div
              key={ribbon.id}
              className="login-wave"
              style={{
                top: ribbon.top,
                opacity: ribbon.opacity,
                transform: `translateZ(${ribbon.depth})`,
              }}
            >
              <svg
                className="login-wave__sheet"
                viewBox="0 0 2000 280"
                preserveAspectRatio="none"
                style={{ animationDuration: ribbon.duration, animationDelay: ribbon.delay }}
              >
                <defs>
                  <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={ribbon.crest} stopOpacity="0.55" />
                    <stop offset="22%" stopColor={ribbon.mid} stopOpacity="0.16" />
                    <stop offset="100%" stopColor={ribbon.mid} stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id={glossId} x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor={ribbon.gloss} stopOpacity="0" />
                    <stop offset="42%" stopColor={ribbon.gloss} stopOpacity="0.15" />
                    <stop offset="50%" stopColor="#ffffff" stopOpacity="0.95" />
                    <stop offset="58%" stopColor={ribbon.gloss} stopOpacity="0.2" />
                    <stop offset="100%" stopColor={ribbon.gloss} stopOpacity="0" />
                  </linearGradient>
                </defs>
                <path d={paths.fill} fill={`url(#${fillId})`} />
                <path
                  className="login-wave__crest"
                  d={paths.crest}
                  fill="none"
                  stroke={`url(#${glossId})`}
                  strokeWidth="2.4"
                  strokeLinecap="round"
                />
              </svg>
            </div>
          );
        })}
      </div>
    </div>
    <div className="login-waves__sheen" />
    <div className="login-waves__vignette" />
  </div>
);

export default LoginWaves;
