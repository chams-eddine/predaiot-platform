'use client';

/**
 * Non-blocking 3D backdrop for the Hero. Deliberately subtle — 2,000 tiny
 * cyan points drifting in a large volume with mouse parallax. Rendered at
 * reduced DPR + antialias off for a cheap fill rate; the point of the scene
 * is atmosphere, not detail.
 *
 * Loaded via next/dynamic({ ssr: false }) from HeroSection so it never
 * touches the server render and never blocks TTI.
 */

import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import * as THREE from 'three';

const POINT_COUNT = 2000;
const FIELD_SIZE = 20;

function NetworkField() {
  const ref = useRef<THREE.Points>(null!);
  const { mouse } = useThree();

  const positions = useMemo(() => {
    const arr = new Float32Array(POINT_COUNT * 3);
    for (let i = 0; i < POINT_COUNT; i++) {
      // Distribute in a wide flat volume — deeper than tall for a sense of horizon
      arr[i * 3]     = (Math.random() - 0.5) * FIELD_SIZE;
      arr[i * 3 + 1] = (Math.random() - 0.5) * FIELD_SIZE * 0.5;
      arr[i * 3 + 2] = (Math.random() - 0.5) * FIELD_SIZE;
    }
    return arr;
  }, []);

  useFrame((state, delta) => {
    if (!ref.current) return;
    // Slow autonomous drift + subtle mouse parallax
    ref.current.rotation.y += delta * 0.02;
    ref.current.rotation.y += mouse.x * 0.0008;
    ref.current.rotation.x  = mouse.y * 0.04;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={POINT_COUNT}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        color="#00FFFF"
        size={0.035}
        sizeAttenuation
        transparent
        opacity={0.55}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

export default function HeroBackground3D() {
  return (
    <Canvas
      camera={{ position: [0, 0, 8], fov: 45 }}
      dpr={[1, 1.5]}
      gl={{ antialias: false, powerPreference: 'high-performance', alpha: true }}
      style={{ background: 'transparent' }}
    >
      <NetworkField />
    </Canvas>
  );
}
