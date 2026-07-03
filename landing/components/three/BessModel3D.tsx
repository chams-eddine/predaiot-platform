"use client";

import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float } from "@react-three/drei";
import * as THREE from "three";

/**
 * Low-poly BESS asset. Black metallic cabinet with side vent slats and a
 * pulsing red leakage indicator LED. Wrapped in <Float> for organic drift +
 * layered with a slow sinusoidal Y rotation for a "on display" feel.
 *
 * The floating leakage tooltip lives in ProofSection as an HTML overlay so
 * the copy can be Tailwind-styled and animated with Framer Motion.
 */
const BatteryAsset = () => {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.3) * 0.15;
    }
  });

  return (
    <Float speed={1.5} rotationIntensity={0.1} floatIntensity={0.5}>
      <group ref={groupRef} position={[0, -0.5, 0]}>
        {/* Main cabinet — black powder-coated steel */}
        <mesh position={[0, 0, 0]} castShadow>
          <boxGeometry args={[2.5, 3.5, 1.5]} />
          <meshStandardMaterial color="#1a1a1a" roughness={0.4} metalness={0.9} />
        </mesh>

        {/* Side vent slats — six horizontal cutouts */}
        {Array.from({ length: 6 }).map((_, i) => (
          <mesh key={i} position={[-1.26, 0.8 - i * 0.35, 0]}>
            <boxGeometry args={[0.05, 0.2, 1.2]} />
            <meshStandardMaterial color="#111111" />
          </mesh>
        ))}

        {/* Leakage indicator LED — red emissive, radiates onto surrounding surface */}
        <pointLight position={[0, 2.2, 0.5]} color="#ff3366" intensity={8} distance={5} />
        <mesh position={[0.8, 1.6, 0.76]}>
          <boxGeometry args={[0.3, 0.15, 0.05]} />
          <meshStandardMaterial
            color="#ff3366"
            emissive="#ff3366"
            emissiveIntensity={4}
          />
        </mesh>
      </group>
    </Float>
  );
};

export default function BessModel3D() {
  return (
    <div className="w-full h-full">
      <Canvas
        camera={{ position: [0, 1, 6], fov: 45 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, powerPreference: "high-performance", alpha: true }}
      >
        <ambientLight intensity={0.3} />
        <directionalLight position={[5, 5, 5]} intensity={1} />
        <BatteryAsset />
      </Canvas>
    </div>
  );
}
