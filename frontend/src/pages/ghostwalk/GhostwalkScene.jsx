import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useMemo, useRef } from "react";
import { readPrefs } from "../../prefs.js";

const PALETTE = {
  bg: "#1a2740",
  floor: "#e8f1ff",
  floorEdge: "#b8d0f0",
  wall: "#4f6fa8",
  wallTop: "#7eb6ff",
  wallAccent: "#3d5a8c",
  goal: "#3ddc84",
  goalGlow: "#1faa5a",
  gem: "#ffc857",
  gemGlow: "#ff8f1f",
  ghost: "#f7fbff",
  ghostRim: "#9ad0ff",
  signRed: "#ff5c7a",
  signBlue: "#4dabff",
};

function FloorTile({ row, col }) {
  return (
    <group position={[col, 0, row]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]} receiveShadow>
        <planeGeometry args={[0.94, 0.94]} />
        <meshStandardMaterial color={PALETTE.floor} roughness={0.85} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0]}>
        <ringGeometry args={[0.42, 0.47, 24]} />
        <meshStandardMaterial color={PALETTE.floorEdge} transparent opacity={0.55} />
      </mesh>
    </group>
  );
}

function Wall({ row, col }) {
  return (
    <group position={[col, 0, row]}>
      <mesh position={[0, 0.72, 0]} castShadow>
        <boxGeometry args={[0.92, 1.35, 0.92]} />
        <meshStandardMaterial color={PALETTE.wall} roughness={0.55} metalness={0.08} />
      </mesh>
      <mesh position={[0, 1.42, 0]}>
        <boxGeometry args={[0.96, 0.12, 0.96]} />
        <meshStandardMaterial
          color={PALETTE.wallTop}
          emissive={PALETTE.wallTop}
          emissiveIntensity={0.35}
          roughness={0.4}
        />
      </mesh>
    </group>
  );
}

function Goal({ row, col, reduceMotion }) {
  const pillar = useRef();
  const ring = useRef();
  useFrame((state) => {
    if (reduceMotion) return;
    const t = state.clock.elapsedTime;
    if (pillar.current) {
      pillar.current.scale.y = 1 + Math.sin(t * 2.2) * 0.12;
      pillar.current.material.emissiveIntensity = 0.9 + Math.sin(t * 2.2) * 0.35;
    }
    if (ring.current) {
      ring.current.rotation.z = t * 0.8;
      ring.current.scale.setScalar(1 + Math.sin(t * 2.2) * 0.08);
    }
  });
  return (
    <group position={[col, 0, row]}>
      <mesh position={[0, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.46, 28]} />
        <meshStandardMaterial
          color={PALETTE.goal}
          emissive={PALETTE.goalGlow}
          emissiveIntensity={0.75}
        />
      </mesh>
      <mesh ref={ring} position={[0, 0.06, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.34, 0.44, 28]} />
        <meshStandardMaterial
          color={PALETTE.goal}
          emissive={PALETTE.goal}
          emissiveIntensity={0.6}
          transparent
          opacity={0.9}
        />
      </mesh>
      <mesh ref={pillar} position={[0, 0.7, 0]}>
        <cylinderGeometry args={[0.14, 0.2, 1.25, 16]} />
        <meshStandardMaterial
          color={PALETTE.goal}
          emissive={PALETTE.goalGlow}
          emissiveIntensity={1}
          transparent
          opacity={0.88}
        />
      </mesh>
    </group>
  );
}

function Gem({ row, col, reduceMotion }) {
  const mesh = useRef();
  useFrame((state) => {
    if (reduceMotion || !mesh.current) return;
    const t = state.clock.elapsedTime;
    mesh.current.rotation.y = t * 1.6;
    mesh.current.position.y = 0.55 + Math.sin(t * 2.4 + row + col) * 0.12;
  });
  return (
    <mesh ref={mesh} position={[col, 0.55, row]}>
      <octahedronGeometry args={[0.34, 0]} />
      <meshStandardMaterial
        color={PALETTE.gem}
        emissive={PALETTE.gemGlow}
        emissiveIntensity={0.45}
        metalness={0.45}
        roughness={0.2}
      />
    </mesh>
  );
}

function Sign({ row, col, color }) {
  const fill = color === "red" ? PALETTE.signRed : PALETTE.signBlue;
  return (
    <mesh position={[col, 0.08, row]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[0.78, 0.78]} />
      <meshStandardMaterial color={fill} emissive={fill} emissiveIntensity={0.4} />
    </mesh>
  );
}

function Ghost({ row, col, facing, reduceMotion }) {
  const group = useRef();
  const yaw = { N: Math.PI, E: Math.PI / 2, S: 0, W: -Math.PI / 2 }[facing] || 0;
  useFrame((state) => {
    if (!group.current) return;
    group.current.rotation.y = yaw;
    if (reduceMotion) {
      group.current.position.y = 0.72;
      return;
    }
    group.current.position.y = 0.72 + Math.sin(state.clock.elapsedTime * 2.6) * 0.1;
  });
  return (
    <group ref={group} position={[col, 0.72, row]}>
      <mesh position={[0, -0.62, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.48, 28]} />
        <meshStandardMaterial color="#0b1528" transparent opacity={0.28} />
      </mesh>
      <mesh castShadow>
        <capsuleGeometry args={[0.34, 0.5, 6, 12]} />
        <meshStandardMaterial
          color={PALETTE.ghost}
          emissive={PALETTE.ghostRim}
          emissiveIntensity={0.22}
          roughness={0.35}
        />
      </mesh>
      <mesh position={[0, 0.52, 0]}>
        <sphereGeometry args={[0.34, 24, 24]} />
        <meshStandardMaterial color={PALETTE.ghost} roughness={0.3} />
      </mesh>
      <mesh position={[-0.12, 0.58, 0.26]}>
        <sphereGeometry args={[0.08, 12, 12]} />
        <meshStandardMaterial color="#152033" />
      </mesh>
      <mesh position={[0.12, 0.58, 0.26]}>
        <sphereGeometry args={[0.08, 12, 12]} />
        <meshStandardMaterial color="#152033" />
      </mesh>
      {/* Soft halo so the ghost pops on light floors */}
      <mesh position={[0, 0.2, 0]}>
        <sphereGeometry args={[0.55, 16, 16]} />
        <meshStandardMaterial
          color={PALETTE.ghostRim}
          transparent
          opacity={0.12}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

function WorldContents({ grid, hero, reduceMotion }) {
  const cells = useMemo(() => {
    const list = [];
    (grid || []).forEach((line, row) => {
      const chars = typeof line === "string" ? line : line.join("");
      [...chars].forEach((cell, col) => {
        if (cell === "#") list.push({ type: "wall", row, col });
        else {
          list.push({ type: "floor", row, col });
          if (cell === "G") list.push({ type: "goal", row, col });
          if (cell === "*") list.push({ type: "gem", row, col });
          if (cell === "r") list.push({ type: "sign", row, col, color: "red" });
          if (cell === "b") list.push({ type: "sign", row, col, color: "blue" });
        }
      });
    });
    return list;
  }, [grid]);

  return (
    <>
      <color attach="background" args={[PALETTE.bg]} />
      <fog attach="fog" args={[PALETTE.bg, 14, 36]} />
      <ambientLight intensity={0.85} />
      <hemisphereLight args={["#9ec9ff", "#1a2740", 0.55]} />
      <directionalLight position={[7, 14, 6]} intensity={1.35} castShadow color="#fff4e0" />
      <pointLight position={[0, 4, 0]} intensity={0.45} color="#7eb6ff" distance={28} />
      {cells.map((cell) => {
        const key = `${cell.type}-${cell.row}-${cell.col}`;
        if (cell.type === "floor") return <FloorTile key={key} row={cell.row} col={cell.col} />;
        if (cell.type === "wall") return <Wall key={key} row={cell.row} col={cell.col} />;
        if (cell.type === "goal") {
          return <Goal key={key} row={cell.row} col={cell.col} reduceMotion={reduceMotion} />;
        }
        if (cell.type === "gem") {
          return <Gem key={key} row={cell.row} col={cell.col} reduceMotion={reduceMotion} />;
        }
        if (cell.type === "sign") {
          return <Sign key={key} row={cell.row} col={cell.col} color={cell.color} />;
        }
        return null;
      })}
      {hero ? (
        <Ghost
          row={hero.row}
          col={hero.col}
          facing={hero.facing || "E"}
          reduceMotion={reduceMotion}
        />
      ) : null}
    </>
  );
}

function cameraForGrid(rows, cols, topDown) {
  const span = Math.max(rows, cols, 3);
  const center = [(cols - 1) / 2, 0, (rows - 1) / 2];
  if (topDown) {
    const zoom = Math.max(20, Math.min(52, 170 / span));
    return {
      center,
      camera: { position: [center[0], 18, center[2] + 0.01], zoom, near: 0.1, far: 100 },
      minDistance: 3,
      maxDistance: 30,
    };
  }
  const distance = Math.max(5.2, span * 1.05);
  return {
    center,
    camera: {
      position: [center[0] + distance * 0.5, distance * 0.78, center[2] + distance * 0.72],
      fov: 36,
      near: 0.1,
      far: 100,
    },
    minDistance: 3,
    maxDistance: Math.max(18, span * 2.5),
  };
}

export default function GhostwalkScene({
  grid,
  hero,
  topDown = false,
  reduceMotion = false,
}) {
  const prefs = readPrefs();
  const quiet = reduceMotion || prefs.reduceMotion;
  const rows = grid?.length || 3;
  const cols = (typeof grid?.[0] === "string" ? grid[0].length : grid?.[0]?.length) || 3;
  const framing = cameraForGrid(rows, cols, topDown);

  return (
    <div className="ghostwalk-canvas h-full min-h-[16rem] w-full overflow-hidden rounded-2xl border-2 border-[color-mix(in_srgb,#7eb6ff_55%,transparent)] bg-[#1a2740] shadow-[0_0_0_1px_rgba(126,182,255,0.15),0_12px_40px_rgba(10,20,40,0.45)]">
      <Canvas
        key={topDown ? "top" : "persp"}
        shadows
        orthographic={topDown}
        camera={framing.camera}
        aria-label="Ghostwalk 3D world"
      >
        <WorldContents grid={grid} hero={hero} reduceMotion={quiet} />
        <OrbitControls
          enablePan={false}
          minDistance={framing.minDistance}
          maxDistance={framing.maxDistance}
          maxPolarAngle={topDown ? 0.01 : Math.PI / 2.15}
          target={framing.center}
        />
      </Canvas>
    </div>
  );
}
