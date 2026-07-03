"use client";

import { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

/**
 * Hero backdrop — the "Economic Core". A central emissive icosahedron
 * wrapped in a slowly counter-rotating wireframe shell, surrounded by
 * ~2,000 particles distributed on a spherical shell. The whole rig gets
 * subtle mouse parallax so pointer motion tilts the scene toward the
 * viewer — creates presence without stealing attention from the CTA.
 *
 * Performance choices:
 *   - dpr capped at 1.5, antialias off (particles look fine, and this
 *     scene has to stay <2ms per frame on entry-level laptops)
 *   - Points use AdditiveBlending, depthWrite off — cheap fill
 *   - No shadow map — one pointLight only
 */

function CoreSphere() {
  const innerRef = useRef<THREE.Mesh>(null);
  const shellRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (innerRef.current) {
      innerRef.current.rotation.y = t * 0.18;
      innerRef.current.rotation.x = t * 0.09;
    }
    if (shellRef.current) {
      // Counter-rotate to give a "gyroscopic" feel
      shellRef.current.rotation.y = -t * 0.10;
      shellRef.current.rotation.z = t * 0.06;
    }
  });

  return (
    <group>
      <mesh ref={innerRef}>
        <icosahedronGeometry args={[1.2, 1]} />
        <meshStandardMaterial
          color="#00FFFF"
          emissive="#00FFFF"
          emissiveIntensity={0.9}
          transparent
          opacity={0.35}
        />
      </mesh>

      <mesh ref={shellRef}>
        <icosahedronGeometry args={[1.85, 1]} />
        <meshBasicMaterial
          color="#00FFFF"
          wireframe
          transparent
          opacity={0.28}
        />
      </mesh>

      <pointLight color="#00FFFF" intensity={4} distance={12} />
    </group>
  );
}

function ParticleField() {
  const ref = useRef<THREE.Points>(null);

  const positions = useMemo(() => {
    const count = 2000;
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      // Distribute on a spherical shell between r=4 and r=12 — leaves a
      // clean empty zone in the middle for the core to sit inside.
      const r = 4 + Math.random() * 8;
      const theta = Math.random() * 2 * Math.PI;
      const phi = Math.acos(2 * Math.random() - 1);
      arr[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
      arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      arr[i * 3 + 2] = r * Math.cos(phi);
    }
    return arr;
  }, []);

  useFrame((_state, delta) => {
    if (ref.current) {
      ref.current.rotation.y += delta * 0.02;
    }
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={positions.length / 3}
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

function MouseParallax({ children }: { children: React.ReactNode }) {
  const groupRef = useRef<THREE.Group>(null);
  const { mouse } = useThree();

  useFrame(() => {
    if (groupRef.current) {
      // Damped follow — the group settles toward the target orientation
      const targetY = mouse.x * 0.15;
      const targetX = mouse.y * 0.10;
      groupRef.current.rotation.y += (targetY - groupRef.current.rotation.y) * 0.05;
      groupRef.current.rotation.x += (targetX - groupRef.current.rotation.x) * 0.05;
    }
  });

  return <group ref={groupRef}>{children}</group>;
}

export default function EconomicCore3D() {
  return (
    <div className="absolute inset-0 w-full h-full">
      <Canvas
        camera={{ position: [0, 0, 6], fov: 50 }}
        dpr={[1, 1.5]}
        gl={{
          antialias: false,
          powerPreference: "high-performance",
          alpha: true,
        }}
      >
        <ambientLight intensity={0.15} />
        <MouseParallax>
          <CoreSphere />
          <ParticleField />
        </MouseParallax>
      </Canvas>
    </div>
  );
}
