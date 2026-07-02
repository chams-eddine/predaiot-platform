'use client';

/**
 * Interactive 3D BESS visualisation. Not a spinning cube — a low-poly
 * representation of a stacked battery cabinet with:
 *   - 6 modules laid out 3×2 on a metal platform
 *   - Slow group rotation for depth
 *   - Emissive cyan pulse per-module, phase-offset so they blink out of sync
 *   - HTML tooltip floating above the stack showing live leakage figure
 *
 * Performance choices:
 *   - dpr capped at 1.5 (retina but not 3x)
 *   - antialiasing on (the geometry is chunky, cheap enough)
 *   - OrbitControls zoom/pan disabled → single interaction surface = rotate
 *   - Polar range restricted so the user can't spin under the ground
 */

import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import { Suspense, useRef } from 'react';
import * as THREE from 'three';

const MODULE_POSITIONS: Array<[number, number, number]> = [
  [-1.1, 0, -0.45], [0, 0, -0.45], [1.1, 0, -0.45],
  [-1.1, 0,  0.45], [0, 0,  0.45], [1.1, 0,  0.45],
];

function BatteryModule({
  position,
  phaseOffset,
}: {
  position: [number, number, number];
  phaseOffset: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null!);

  useFrame((state) => {
    if (!meshRef.current) return;
    const t = state.clock.elapsedTime + phaseOffset;
    // Emissive pulse — floor at 0.15, peak at 0.55
    const intensity = 0.35 + 0.20 * Math.sin(t * 1.4);
    const mat = meshRef.current.material as THREE.MeshStandardMaterial;
    mat.emissiveIntensity = intensity;
  });

  return (
    <mesh ref={meshRef} position={position} castShadow receiveShadow>
      <boxGeometry args={[0.9, 1.4, 0.6]} />
      <meshStandardMaterial
        color="#0A1420"
        emissive="#00FFFF"
        emissiveIntensity={0.35}
        metalness={0.85}
        roughness={0.25}
      />
    </mesh>
  );
}

function BESSAsset() {
  const groupRef = useRef<THREE.Group>(null!);

  useFrame((state, delta) => {
    // Very slow group spin — 24° / second felt right for "on display"
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.12;
    }
  });

  return (
    <group ref={groupRef} position={[0, -0.1, 0]}>
      {MODULE_POSITIONS.map((pos, i) => (
        <BatteryModule
          key={i}
          position={pos}
          phaseOffset={i * 0.55 /* stagger the pulses */}
        />
      ))}

      {/* Steel platform under the modules */}
      <mesh position={[0, -0.83, 0]} receiveShadow>
        <boxGeometry args={[3.7, 0.15, 1.55]} />
        <meshStandardMaterial
          color="#1A2532"
          metalness={0.7}
          roughness={0.5}
        />
      </mesh>

      {/* Support legs — 4 corners */}
      {([[-1.6, -1, -0.6], [1.6, -1, -0.6], [-1.6, -1, 0.6], [1.6, -1, 0.6]] as const).map(
        (pos, i) => (
          <mesh key={i} position={pos}>
            <boxGeometry args={[0.15, 0.35, 0.15]} />
            <meshStandardMaterial color="#0F1520" metalness={0.6} roughness={0.6} />
          </mesh>
        )
      )}

      {/* Grid connection pole */}
      <mesh position={[2.4, -0.2, 0]}>
        <cylinderGeometry args={[0.05, 0.05, 2.4, 6]} />
        <meshStandardMaterial color="#2A3B4A" metalness={0.5} roughness={0.6} />
      </mesh>
      <mesh position={[2.4, 0.9, 0]}>
        <boxGeometry args={[0.9, 0.1, 0.1]} />
        <meshStandardMaterial color="#2A3B4A" metalness={0.5} roughness={0.6} />
      </mesh>

      {/* Live-leakage tooltip — the whole point of the visualisation */}
      <Html
        position={[0, 2.15, 0]}
        center
        distanceFactor={7}
        occlude={false}
      >
        <div
          className="
            pointer-events-none whitespace-nowrap
            ps-4 pe-4 py-2.5 rounded-xl
            backdrop-blur-md
            bg-black/70 border border-brand-red/40
            shadow-glow-red
          "
        >
          <div className="text-[10px] tracking-[0.18em] text-white/50 uppercase font-semibold mb-0.5">
            Live Leakage · 24h
          </div>
          <div
            className="text-2xl font-black text-brand-red tabular-nums leading-none"
            style={{ fontFamily: 'var(--font-mono), JetBrains Mono, monospace' }}
          >
            −$1,205
          </div>
        </div>
      </Html>
    </group>
  );
}

export default function InteractiveAsset3D() {
  return (
    <div
      className="
        relative w-full aspect-square md:aspect-[4/3] lg:aspect-square
        rounded-2xl overflow-hidden
        bg-gradient-to-br from-canvas-card via-canvas to-canvas
        border border-canvas-hairline
      "
    >
      {/* Radial glow behind the asset */}
      <div
        className="
          absolute inset-0 pointer-events-none
          bg-radial-cyan opacity-70
        "
        aria-hidden="true"
      />

      {/* Corner gauge marks — pure decoration to feel industrial */}
      <div className="absolute top-4 start-4 text-[9px] tracking-[0.25em] text-white/40 font-mono">
        BESS-500 · IBRI-2
      </div>
      <div className="absolute top-4 end-4 text-[9px] tracking-[0.25em] text-brand-cyan font-mono flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-brand-cyan animate-pulse" />
        LIVE
      </div>
      <div className="absolute bottom-4 start-4 text-[9px] tracking-[0.25em] text-white/40 font-mono">
        DQ Score · 34.3%
      </div>
      <div className="absolute bottom-4 end-4 text-[9px] tracking-[0.25em] text-white/40 font-mono">
        Ann. Leakage · $1.89M
      </div>

      <Canvas
        camera={{ position: [4.5, 3.2, 5.2], fov: 40 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, powerPreference: 'high-performance', alpha: true }}
        shadows={false /* single directional light, no shadow map budget */}
        style={{ background: 'transparent' }}
      >
        <Suspense fallback={null}>
          <ambientLight intensity={0.35} />
          <pointLight position={[5, 6, 5]}   intensity={2.0} color="#00FFFF" distance={20} />
          <pointLight position={[-5, 2, -3]} intensity={0.8} color="#ffffff" distance={15} />
          <BESSAsset />
          <OrbitControls
            enableZoom={false}
            enablePan={false}
            autoRotate={false}
            minPolarAngle={Math.PI * 0.28}
            maxPolarAngle={Math.PI * 0.55}
            enableDamping
            dampingFactor={0.06}
          />
        </Suspense>
      </Canvas>
    </div>
  );
}
