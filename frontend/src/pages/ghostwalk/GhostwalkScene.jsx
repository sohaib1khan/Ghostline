import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useMemo } from "react";
import { readPrefs } from "../../prefs.js";

const TILE = 1;

function Floor({ rows, cols, highContrast }) {
  const color = highContrast ? "#e8eef5" : "#c5d4e0";
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[(cols - 1) / 2, 0, (rows - 1) / 2]} receiveShadow>
      <planeGeometry args={[cols * TILE, rows * TILE]} />
      <meshStandardMaterial color={color} />
    </mesh>
  );
}

function Wall({ row, col, highContrast }) {
  return (
    <mesh position={[col, 0.55, row]} castShadow>
      <boxGeometry args={[0.92, 1.1, 0.92]} />
      <meshStandardMaterial color={highContrast ? "#1a1a1a" : "#3d4450"} />
    </mesh>
  );
}

function Goal({ row, col, highContrast }) {
  return (
    <mesh position={[col, 0.05, row]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[0.9, 0.9]} />
      <meshStandardMaterial
        color={highContrast ? "#00c853" : "#7d9b76"}
        emissive={highContrast ? "#00c853" : "#5a7a55"}
        emissiveIntensity={0.45}
      />
    </mesh>
  );
}

function Gem({ row, col, reduceMotion }) {
  return (
    <mesh position={[col, 0.45, row]}>
      <octahedronGeometry args={[0.22, 0]} />
      <meshStandardMaterial color="#d4a017" metalness={0.4} roughness={0.3} />
      {!reduceMotion ? null : null}
    </mesh>
  );
}

function Sign({ row, col, color }) {
  return (
    <mesh position={[col, 0.06, row]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[0.7, 0.7]} />
      <meshStandardMaterial color={color === "red" ? "#c62828" : "#1565c0"} />
    </mesh>
  );
}

function Ghost({ row, col, facing, reduceMotion, bob }) {
  const yaw = { N: Math.PI, E: Math.PI / 2, S: 0, W: -Math.PI / 2 }[facing] || 0;
  const y = reduceMotion ? 0.55 : 0.55 + bob * 0.08;
  return (
    <group position={[col, y, row]} rotation={[0, yaw, 0]}>
      <mesh castShadow>
        <capsuleGeometry args={[0.22, 0.35, 4, 8]} />
        <meshStandardMaterial color="#f2f5f8" />
      </mesh>
      <mesh position={[0, 0.35, 0]}>
        <sphereGeometry args={[0.22, 16, 16]} />
        <meshStandardMaterial color="#f2f5f8" />
      </mesh>
      <mesh position={[-0.08, 0.4, 0.16]}>
        <sphereGeometry args={[0.04, 8, 8]} />
        <meshStandardMaterial color="#222" />
      </mesh>
      <mesh position={[0.08, 0.4, 0.16]}>
        <sphereGeometry args={[0.04, 8, 8]} />
        <meshStandardMaterial color="#222" />
      </mesh>
    </group>
  );
}

function WorldContents({ grid, hero, reduceMotion, highContrast, bob }) {
  const cells = useMemo(() => {
    const list = [];
    (grid || []).forEach((line, row) => {
      const chars = typeof line === "string" ? line : line.join("");
      [...chars].forEach((cell, col) => {
        if (cell === "#") list.push({ type: "wall", row, col });
        else if (cell === "G") list.push({ type: "goal", row, col });
        else if (cell === "*") list.push({ type: "gem", row, col });
        else if (cell === "r") list.push({ type: "sign", row, col, color: "red" });
        else if (cell === "b") list.push({ type: "sign", row, col, color: "blue" });
      });
    });
    return list;
  }, [grid]);

  const rows = grid?.length || 1;
  const cols = (typeof grid?.[0] === "string" ? grid[0].length : grid?.[0]?.length) || 1;

  return (
    <>
      <ambientLight intensity={0.7} />
      <directionalLight position={[8, 12, 6]} intensity={1.1} castShadow />
      <Floor rows={rows} cols={cols} highContrast={highContrast} />
      {cells.map((cell) => {
        const key = `${cell.type}-${cell.row}-${cell.col}`;
        if (cell.type === "wall") return <Wall key={key} row={cell.row} col={cell.col} highContrast={highContrast} />;
        if (cell.type === "goal") return <Goal key={key} row={cell.row} col={cell.col} highContrast={highContrast} />;
        if (cell.type === "gem") return <Gem key={key} row={cell.row} col={cell.col} reduceMotion={reduceMotion} />;
        if (cell.type === "sign") return <Sign key={key} row={cell.row} col={cell.col} color={cell.color} />;
        return null;
      })}
      {hero ? (
        <Ghost
          row={hero.row}
          col={hero.col}
          facing={hero.facing || "E"}
          reduceMotion={reduceMotion}
          bob={bob}
        />
      ) : null}
    </>
  );
}

export default function GhostwalkScene({
  grid,
  hero,
  topDown = false,
  reduceMotion = false,
}) {
  const prefs = readPrefs();
  const highContrast = prefs.contrast !== "calm";
  const rows = grid?.length || 3;
  const cols = (typeof grid?.[0] === "string" ? grid[0].length : grid?.[0]?.length) || 3;
  const center = [(cols - 1) / 2, 0, (rows - 1) / 2];

  return (
    <div className="h-full min-h-[240px] w-full overflow-hidden rounded-xl bg-[#1b222c]">
      <Canvas
        shadows
        orthographic={topDown}
        camera={
          topDown
            ? { position: [center[0], 14, center[2]], zoom: 28, near: 0.1, far: 100 }
            : { position: [center[0] + 6, 8, center[2] + 7], fov: 42, near: 0.1, far: 100 }
        }
        aria-label="Ghostwalk 3D world"
      >
        <WorldContents
          grid={grid}
          hero={hero}
          reduceMotion={reduceMotion}
          highContrast={highContrast}
          bob={0}
        />
        <OrbitControls
          enablePan={false}
          minDistance={4}
          maxDistance={24}
          maxPolarAngle={topDown ? 0.01 : Math.PI / 2.2}
          target={center}
        />
      </Canvas>
    </div>
  );
}
