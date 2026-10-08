"use client";

import { Float, Sparkles } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useRef, useState } from "react";
import type { Group } from "three";

import { creativeHouses, type CreativeHouse } from "../../src/creative-houses";

function Building({ house }: { house: CreativeHouse }) {
  const group = useRef<Group>(null);
  const [hovered, setHovered] = useState(false);
  const height = house.id === "chat" ? 1.35 : house.id === "agents" ? 1.05 : 0.82;

  useFrame((_, delta) => {
    if (!group.current) return;
    const target = hovered ? 1.16 : 1;
    group.current.scale.x += (target - group.current.scale.x) * Math.min(1, delta * 9);
    group.current.scale.y += (target - group.current.scale.y) * Math.min(1, delta * 9);
    group.current.scale.z += (target - group.current.scale.z) * Math.min(1, delta * 9);
  });

  return <group ref={group} position={house.scenePosition} onClick={() => window.location.assign(house.href)} onPointerOver={(event) => { event.stopPropagation(); setHovered(true); document.body.style.cursor = "pointer"; }} onPointerOut={() => { setHovered(false); document.body.style.cursor = "auto"; }}>
    <mesh position={[0, height / 2, 0]} castShadow receiveShadow><boxGeometry args={[0.86, height, 0.76]} /><meshStandardMaterial color={house.color} emissive={hovered ? house.color : "#000000"} emissiveIntensity={hovered ? 0.42 : 0} roughness={0.5} /></mesh>
    <mesh position={[0, height + 0.28, 0]} rotation={[0, Math.PI / 4, 0]} castShadow><coneGeometry args={[0.72, 0.58, 4]} /><meshStandardMaterial color="#fff1d5" roughness={0.72} /></mesh>
    <mesh position={[0, 0.23, 0.39]}><boxGeometry args={[0.19, 0.36, 0.03]} /><meshStandardMaterial color="#fff6b0" emissive="#fff6b0" emissiveIntensity={hovered ? 1.4 : 0.35} /></mesh>
    <mesh position={[-0.26, height * 0.68, 0.39]}><sphereGeometry args={[0.1, 16, 16]} /><meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={hovered ? 1.2 : 0.2} /></mesh>
  </group>;
}

function BookWorld() {
  const world = useRef<Group>(null);
  const { pointer } = useThree();
  useFrame((_, delta) => {
    if (!world.current) return;
    world.current.rotation.y += (pointer.x * 0.1 - world.current.rotation.y) * Math.min(1, delta * 1.8);
    world.current.rotation.x += (-0.1 - pointer.y * 0.035 - world.current.rotation.x) * Math.min(1, delta * 1.8);
  });
  return <group ref={world} rotation={[-0.1, 0, 0]}>
    <mesh position={[0, -0.29, 0]} receiveShadow><boxGeometry args={[8.4, 0.32, 5.2]} /><meshStandardMaterial color="#f3bd71" roughness={0.8} /></mesh>
    <mesh position={[-2.04, 0, 0]} rotation={[0, -0.025, 0]} receiveShadow><boxGeometry args={[4.02, 0.28, 4.82]} /><meshStandardMaterial color="#fff7db" roughness={0.95} /></mesh>
    <mesh position={[2.04, 0, 0]} rotation={[0, 0.025, 0]} receiveShadow><boxGeometry args={[4.02, 0.28, 4.82]} /><meshStandardMaterial color="#fff7db" roughness={0.95} /></mesh>
    <mesh position={[0, 0.2, 0]} receiveShadow><boxGeometry args={[0.18, 0.18, 4.9]} /><meshStandardMaterial color="#e2ca98" roughness={0.8} /></mesh>
    <mesh position={[0, 0.23, 0.1]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[0.74, 5.2, 20, 1]} /><meshStandardMaterial color="#55d4ed" emissive="#2bb6d6" emissiveIntensity={0.38} roughness={0.25} /></mesh>
    <mesh position={[0, 0.27, 1.95]} rotation={[-Math.PI / 2, 0, 0]}><torusGeometry args={[0.45, 0.09, 12, 30]} /><meshStandardMaterial color="#fff4aa" emissive="#fff4aa" emissiveIntensity={0.8} /></mesh>
    {creativeHouses.map((house) => <Building key={house.id} house={house} />)}
  </group>;
}

function Scene() {
  return <><color attach="background" args={["#bceaff"]} /><fog attach="fog" args={["#bceaff", 9, 18]} /><ambientLight intensity={1.25} /><directionalLight position={[4, 8, 5]} intensity={2.4} castShadow /><pointLight position={[0, 3, 2]} color="#a7f5ff" intensity={4} distance={8} /><Sparkles count={70} scale={[10, 4, 7]} size={2.2} speed={0.35} color="#fff4a5" /><Float speed={1.1} rotationIntensity={0.08} floatIntensity={0.16}><BookWorld /></Float></>;
}

export function CreativeBook3D() {
  return <div className="creative-book-canvas"><Canvas shadows dpr={[1, 1.5]} camera={{ position: [0, 6.4, 9.6], fov: 41 }}><Scene /></Canvas><nav className="creative-book-overlay" aria-label="3D 创作入口">{creativeHouses.map((house) => <a key={house.id} href={house.href} className={`creative-book-overlay__link creative-book-overlay__link--${house.id}`}><span className="creative-book-overlay__icon">{house.icon}</span><span>{house.label}</span><small>{house.hint}</small></a>)}</nav></div>;
}
