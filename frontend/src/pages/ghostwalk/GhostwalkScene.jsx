import { Canvas, useFrame } from "@react-three/fiber";
import {
  ContactShadows,
  Float,
  OrbitControls,
  RoundedBox,
  SoftShadows,
  Sparkles,
  Stars,
} from "@react-three/drei";
import { useMemo, useRef } from "react";
import { themeFor } from "../../ghostwalk/themes.js";
import { readPrefs } from "../../prefs.js";

/** Active theme palette — set by GhostwalkScene before each Canvas render. */
let PALETTE = themeFor("python").palette;
let THEME_SHAPES = themeFor("python").shapes;

function Island({ rows, cols }) {
  const width = cols + 3.4;
  const depth = rows + 3.4;
  const cx = (cols - 1) / 2;
  const cz = (rows - 1) / 2;
  return (
    <group position={[cx, 0, cz]}>
      {/* Deep pedestal */}
      <mesh position={[0, -0.55, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[Math.max(width, depth) * 0.42, Math.max(width, depth) * 0.48, 1.0, 48]} />
        <meshStandardMaterial color={PALETTE.island} roughness={0.92} />
      </mesh>
      <mesh position={[0, -1.35, 0]} castShadow>
        <cylinderGeometry args={[Math.max(width, depth) * 0.34, Math.max(width, depth) * 0.42, 0.9, 40]} />
        <meshStandardMaterial color="#18263c" roughness={1} />
      </mesh>
      {/* Soft grassy ring */}
      <mesh position={[0, -0.02, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <ringGeometry args={[Math.max(width, depth) * 0.28, Math.max(width, depth) * 0.4, 64]} />
        <meshStandardMaterial color={PALETTE.grass} roughness={1} />
      </mesh>
      {/* Rim glow */}
      <mesh position={[0, -0.01, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[Math.max(width, depth) * 0.395, Math.max(width, depth) * 0.42, 64]} />
        <meshStandardMaterial
          color={PALETTE.islandRim}
          emissive={PALETTE.floorGlow}
          emissiveIntensity={0.25}
          transparent
          opacity={0.85}
        />
      </mesh>
      {/* Distant rocks for depth */}
      {[
        [-width * 0.55, -0.1, depth * 0.15],
        [width * 0.5, -0.05, -depth * 0.35],
        [-width * 0.2, -0.15, depth * 0.55],
        [width * 0.35, -0.12, depth * 0.48],
      ].map(([x, y, z], index) => (
        <mesh key={index} position={[x, y, z]} castShadow>
          <icosahedronGeometry args={[0.35 + (index % 3) * 0.12, 0]} />
          <meshStandardMaterial color={index % 2 ? "#2a3d58" : "#334866"} roughness={0.95} />
        </mesh>
      ))}
    </group>
  );
}

function FloorTile({ row, col }) {
  return (
    <group position={[col, 0, row]}>
      <RoundedBox args={[0.96, 0.14, 0.96]} radius={0.06} smoothness={4} position={[0, 0.07, 0]} receiveShadow>
        <meshStandardMaterial color={PALETTE.floor} roughness={0.72} metalness={0.05} />
      </RoundedBox>
      <mesh position={[0, 0.15, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.28, 0.34, 24]} />
        <meshStandardMaterial
          color={PALETTE.floorGlow}
          emissive={PALETTE.floorGlow}
          emissiveIntensity={0.2}
          transparent
          opacity={0.55}
        />
      </mesh>
      <mesh position={[0, 0.145, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.18, 20]} />
        <meshStandardMaterial color={PALETTE.floorInset} roughness={0.8} />
      </mesh>
    </group>
  );
}

function Wall({ row, col }) {
  return (
    <group position={[col, 0, row]}>
      <RoundedBox args={[0.94, 1.45, 0.94]} radius={0.08} smoothness={4} position={[0, 0.78, 0]} castShadow receiveShadow>
        <meshStandardMaterial color={PALETTE.wall} roughness={0.48} metalness={0.12} />
      </RoundedBox>
      {/* Mid band */}
      <mesh position={[0, 0.95, 0]}>
        <boxGeometry args={[0.98, 0.12, 0.98]} />
        <meshStandardMaterial color={PALETTE.wallMid} roughness={0.4} metalness={0.18} />
      </mesh>
      {/* Lit cap */}
      <RoundedBox args={[1.0, 0.16, 1.0]} radius={0.05} smoothness={3} position={[0, 1.55, 0]}>
        <meshStandardMaterial
          color={PALETTE.wallCap}
          emissive={PALETTE.wallCap}
          emissiveIntensity={0.45}
          roughness={0.3}
          metalness={0.2}
        />
      </RoundedBox>
      {/* Tiny lantern stud */}
      <mesh position={[0, 1.72, 0]}>
        <sphereGeometry args={[0.08, 12, 12]} />
        <meshStandardMaterial
          color="#dff0ff"
          emissive="#9ad4ff"
          emissiveIntensity={0.9}
        />
      </mesh>
    </group>
  );
}

function Goal({ row, col, reduceMotion }) {
  const beam = useRef();
  const halo = useRef();
  useFrame((state) => {
    if (reduceMotion) return;
    const t = state.clock.elapsedTime;
    if (beam.current) {
      beam.current.material.opacity = 0.28 + Math.sin(t * 2.1) * 0.1;
      beam.current.scale.y = 1 + Math.sin(t * 2.1) * 0.08;
    }
    if (halo.current) {
      halo.current.rotation.y = t * 0.9;
      halo.current.scale.setScalar(1 + Math.sin(t * 2.4) * 0.06);
    }
  });
  return (
    <group position={[col, 0, row]}>
      <RoundedBox args={[0.92, 0.12, 0.92]} radius={0.05} position={[0, 0.12, 0]} receiveShadow>
        <meshStandardMaterial
          color={PALETTE.goal}
          emissive={PALETTE.goalCore}
          emissiveIntensity={0.7}
          roughness={0.35}
        />
      </RoundedBox>
      {/* Portal arch */}
      <mesh position={[0, 0.95, 0]} rotation={[0, 0, Math.PI / 2]}>
        <torusGeometry args={[0.42, 0.06, 12, 28, Math.PI]} />
        <meshStandardMaterial
          color={PALETTE.goal}
          emissive={PALETTE.goalCore}
          emissiveIntensity={0.85}
          metalness={0.3}
          roughness={0.25}
        />
      </mesh>
      <mesh ref={halo} position={[0, 0.55, 0]}>
        <torusGeometry args={[0.32, 0.035, 10, 28]} />
        <meshStandardMaterial
          color={PALETTE.goal}
          emissive={PALETTE.goal}
          emissiveIntensity={0.7}
          transparent
          opacity={0.9}
        />
      </mesh>
      <mesh ref={beam} position={[0, 1.5, 0]}>
        <cylinderGeometry args={[0.08, 0.22, 2.4, 16]} />
        <meshStandardMaterial
          color={PALETTE.goal}
          emissive={PALETTE.goal}
          emissiveIntensity={1.2}
          transparent
          opacity={0.32}
          depthWrite={false}
        />
      </mesh>
      {!reduceMotion ? (
        <Sparkles
          count={18}
          scale={[1.2, 2.2, 1.2]}
          size={2.5}
          speed={0.35}
          opacity={0.65}
          color={PALETTE.goal}
          position={[0, 1.1, 0]}
        />
      ) : null}
      <pointLight position={[0, 1.2, 0]} intensity={1.1} color={PALETTE.goal} distance={5} />
    </group>
  );
}

function GemShape() {
  const shape = THEME_SHAPES?.gem || "octahedron";
  if (shape === "cube") return <boxGeometry args={[0.42, 0.42, 0.42]} />;
  if (shape === "card") return <boxGeometry args={[0.5, 0.08, 0.36]} />;
  if (shape === "nugget") return <dodecahedronGeometry args={[0.28, 0]} />;
  if (shape === "capsule") return <capsuleGeometry args={[0.16, 0.28, 6, 12]} />;
  if (shape === "bean") return <sphereGeometry args={[0.22, 10, 8]} />;
  if (shape === "disc") return <cylinderGeometry args={[0.28, 0.28, 0.08, 24]} />;
  return <octahedronGeometry args={[0.32, 0]} />;
}

function Gem({ row, col, reduceMotion }) {
  const inner = (
    <group position={[col, 0.55, row]}>
      <mesh castShadow>
        <GemShape />
        <meshStandardMaterial
          color={PALETTE.gem}
          emissive={PALETTE.gemCore}
          emissiveIntensity={0.55}
          metalness={0.55}
          roughness={0.15}
        />
      </mesh>
      <pointLight intensity={0.45} color={PALETTE.gem} distance={2.5} />
    </group>
  );
  if (reduceMotion) return inner;
  return (
    <Float speed={2.2} rotationIntensity={0.6} floatIntensity={0.55}>
      {inner}
    </Float>
  );
}

function Sign({ row, col, color }) {
  const fill = color === "red" ? PALETTE.signRed : PALETTE.signBlue;
  // Always show a left/right arrow as well as color (color alone is not enough).
  const arrow = color === "red" ? "←" : "→";
  return (
    <group position={[col, 0, row]}>
      <RoundedBox args={[0.72, 0.1, 0.72]} radius={0.04} position={[0, 0.12, 0]}>
        <meshStandardMaterial color={fill} emissive={fill} emissiveIntensity={0.45} />
      </RoundedBox>
      <mesh position={[0, 0.42, 0]}>
        <cylinderGeometry args={[0.04, 0.05, 0.55, 10]} />
        <meshStandardMaterial color="#dfe9f5" metalness={0.3} roughness={0.35} />
      </mesh>
      <mesh position={[0, 0.78, 0]}>
        <boxGeometry args={[0.42, 0.28, 0.06]} />
        <meshStandardMaterial color={fill} emissive={fill} emissiveIntensity={0.35} />
      </mesh>
      {/* Direction notch: red = left chevron block, blue = right */}
      <mesh position={[color === "red" ? -0.12 : 0.12, 0.78, 0.04]} rotation={[0, 0, color === "red" ? 0.6 : -0.6]}>
        <boxGeometry args={[0.16, 0.08, 0.04]} />
        <meshStandardMaterial color="#fff" />
      </mesh>
      <mesh visible={false} userData={{ arrow }} />
    </group>
  );
}

function Soil({ row, col, kind }) {
  const raised = kind === "crop" ? 0.22 : kind === "seed" ? 0.12 : 0.06;
  return (
    <group position={[col, 0, row]}>
      <RoundedBox args={[0.88, 0.14, 0.88]} radius={0.05} position={[0, 0.1, 0]}>
        <meshStandardMaterial color={PALETTE.soil} roughness={0.92} />
      </RoundedBox>
      {kind === "seed" ? (
        <mesh position={[0, 0.22, 0]}>
          <sphereGeometry args={[0.1, 10, 10]} />
          <meshStandardMaterial color={PALETTE.seed} roughness={0.7} />
        </mesh>
      ) : null}
      {kind === "crop" ? (
        <group position={[0, raised, 0]}>
          <mesh>
            <sphereGeometry args={[0.16, 12, 12]} />
            <meshStandardMaterial
              color={PALETTE.crop}
              emissive={PALETTE.cropLeaf}
              emissiveIntensity={0.25}
            />
          </mesh>
          <mesh position={[0.12, 0.08, 0.05]} rotation={[0.4, 0.2, 0.3]}>
            <boxGeometry args={[0.18, 0.04, 0.1]} />
            <meshStandardMaterial color={PALETTE.cropLeaf} />
          </mesh>
          <mesh position={[-0.1, 0.1, -0.06]} rotation={[-0.3, 0.4, -0.2]}>
            <boxGeometry args={[0.16, 0.04, 0.1]} />
            <meshStandardMaterial color={PALETTE.cropLeaf} />
          </mesh>
        </group>
      ) : null}
    </group>
  );
}

function Barn({ row, col, reduceMotion }) {
  return (
    <group position={[col, 0, row]}>
      <RoundedBox args={[0.7, 0.55, 0.55]} radius={0.04} position={[0, 0.4, 0]}>
        <meshStandardMaterial color={PALETTE.barn} roughness={0.65} />
      </RoundedBox>
      <mesh position={[0, 0.78, 0]} rotation={[0, Math.PI / 4, 0]}>
        <coneGeometry args={[0.52, 0.36, 4]} />
        <meshStandardMaterial color={PALETTE.barnRoof} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.28, 0.28]}>
        <boxGeometry args={[0.22, 0.32, 0.04]} />
        <meshStandardMaterial color="#3a2418" />
      </mesh>
      {!reduceMotion ? (
        <Sparkles
          count={8}
          scale={[0.9, 1.1, 0.9]}
          size={2}
          speed={0.25}
          opacity={0.5}
          color="#ffd9a0"
          position={[0, 0.9, 0]}
        />
      ) : null}
    </group>
  );
}

function Ghost({ row, col, facing, reduceMotion }) {
  const group = useRef();
  const yaw = { N: Math.PI, E: Math.PI / 2, S: 0, W: -Math.PI / 2 }[facing] || 0;
  useFrame((state) => {
    if (!group.current) return;
    group.current.rotation.y = yaw;
    if (reduceMotion) {
      group.current.position.set(col, 0.78, row);
      return;
    }
    const bob = Math.sin(state.clock.elapsedTime * 2.8) * 0.12;
    group.current.position.set(col, 0.78 + bob, row);
  });
  return (
    <group ref={group} position={[col, 0.78, row]}>
      <mesh position={[0, -0.7, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.5, 28]} />
        <meshStandardMaterial color="#071018" transparent opacity={0.32} />
      </mesh>
      {/* Body */}
      <mesh castShadow>
        <capsuleGeometry args={[0.36, 0.52, 8, 16]} />
        <meshStandardMaterial
          color={PALETTE.ghost}
          emissive={PALETTE.ghostRim}
          emissiveIntensity={0.28}
          roughness={0.28}
        />
      </mesh>
      {/* Head */}
      <mesh position={[0, 0.56, 0]} castShadow>
        <sphereGeometry args={[0.38, 28, 28]} />
        <meshStandardMaterial color={PALETTE.ghost} roughness={0.25} />
      </mesh>
      {/* Soft ears / tufts */}
      <mesh position={[-0.22, 0.88, -0.05]}>
        <sphereGeometry args={[0.12, 12, 12]} />
        <meshStandardMaterial color={PALETTE.ghostShade} />
      </mesh>
      <mesh position={[0.22, 0.88, -0.05]}>
        <sphereGeometry args={[0.12, 12, 12]} />
        <meshStandardMaterial color={PALETTE.ghostShade} />
      </mesh>
      {/* Eyes */}
      <mesh position={[-0.13, 0.62, 0.3]}>
        <sphereGeometry args={[0.09, 14, 14]} />
        <meshStandardMaterial color="#152033" />
      </mesh>
      <mesh position={[0.13, 0.62, 0.3]}>
        <sphereGeometry args={[0.09, 14, 14]} />
        <meshStandardMaterial color="#152033" />
      </mesh>
      <mesh position={[-0.11, 0.65, 0.36]}>
        <sphereGeometry args={[0.03, 8, 8]} />
        <meshStandardMaterial color="#ffffff" />
      </mesh>
      <mesh position={[0.15, 0.65, 0.36]}>
        <sphereGeometry args={[0.03, 8, 8]} />
        <meshStandardMaterial color="#ffffff" />
      </mesh>
      {/* Cheeks */}
      <mesh position={[-0.22, 0.5, 0.28]}>
        <sphereGeometry args={[0.06, 10, 10]} />
        <meshStandardMaterial color={PALETTE.cheek} transparent opacity={0.75} />
      </mesh>
      <mesh position={[0.22, 0.5, 0.28]}>
        <sphereGeometry args={[0.06, 10, 10]} />
        <meshStandardMaterial color={PALETTE.cheek} transparent opacity={0.75} />
      </mesh>
      {/* Arms */}
      <mesh position={[-0.42, 0.15, 0.05]} rotation={[0, 0, 0.5]}>
        <capsuleGeometry args={[0.09, 0.22, 4, 8]} />
        <meshStandardMaterial color={PALETTE.ghost} />
      </mesh>
      <mesh position={[0.42, 0.15, 0.05]} rotation={[0, 0, -0.5]}>
        <capsuleGeometry args={[0.09, 0.22, 4, 8]} />
        <meshStandardMaterial color={PALETTE.ghost} />
      </mesh>
      {/* Aura */}
      <mesh position={[0, 0.15, 0]}>
        <sphereGeometry args={[0.72, 20, 20]} />
        <meshStandardMaterial
          color={PALETTE.ghostRim}
          transparent
          opacity={0.1}
          depthWrite={false}
        />
      </mesh>
      {!reduceMotion ? (
        <Sparkles count={10} scale={1.4} size={1.8} speed={0.25} opacity={0.45} color="#cfe8ff" />
      ) : null}
      <pointLight intensity={0.35} color={PALETTE.ghostRim} distance={3} />
    </group>
  );
}

function WorldAtmosphere({ reduceMotion }) {
  return (
    <>
      <color attach="background" args={[PALETTE.void]} />
      <fog attach="fog" args={[PALETTE.fog, 10, 32]} />
      <Stars radius={60} depth={40} count={reduceMotion ? 400 : 1200} factor={3} saturation={0.4} fade speed={reduceMotion ? 0 : 0.4} />
      <ambientLight intensity={0.55} />
      <hemisphereLight args={["#b9d7ff", "#1a2a18", 0.75]} />
      <directionalLight
        position={[8, 16, 7]}
        intensity={1.55}
        castShadow
        color="#fff1d6"
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-far={40}
        shadow-camera-left={-12}
        shadow-camera-right={12}
        shadow-camera-top={12}
        shadow-camera-bottom={-12}
      />
      <directionalLight position={[-6, 8, -4]} intensity={0.35} color="#8eb7ff" />
      <SoftShadows size={18} samples={12} focus={0.85} />
    </>
  );
}

function WorldContents({ grid, hero, reduceMotion }) {
  const meta = useMemo(() => {
    const list = [];
    let rows = 0;
    let cols = 0;
    (grid || []).forEach((line, row) => {
      const chars = typeof line === "string" ? line : line.join("");
      rows = Math.max(rows, row + 1);
      cols = Math.max(cols, chars.length);
      [...chars].forEach((cell, col) => {
        if (cell === "#") list.push({ type: "wall", row, col });
        else {
          list.push({ type: "floor", row, col });
          if (cell === "G") list.push({ type: "goal", row, col });
          if (cell === "B") list.push({ type: "barn", row, col });
          if (cell === "*") list.push({ type: "gem", row, col });
          if (cell === "~") list.push({ type: "soil", row, col, kind: "empty" });
          if (cell === "s") list.push({ type: "soil", row, col, kind: "seed" });
          if (cell === "c") list.push({ type: "soil", row, col, kind: "crop" });
          if (cell === "r") list.push({ type: "sign", row, col, color: "red" });
          if (cell === "b") list.push({ type: "sign", row, col, color: "blue" });
        }
      });
    });
    return { list, rows: rows || 1, cols: cols || 1 };
  }, [grid]);

  const cx = (meta.cols - 1) / 2;
  const cz = (meta.rows - 1) / 2;

  return (
    <>
      <WorldAtmosphere reduceMotion={reduceMotion} />
      <Island rows={meta.rows} cols={meta.cols} />
      <ContactShadows
        position={[cx, 0.01, cz]}
        opacity={0.45}
        scale={Math.max(meta.rows, meta.cols) + 6}
        blur={2.4}
        far={5}
      />
      {meta.list.map((cell) => {
        const key = `${cell.type}-${cell.row}-${cell.col}`;
        if (cell.type === "floor") return <FloorTile key={key} row={cell.row} col={cell.col} />;
        if (cell.type === "wall") return <Wall key={key} row={cell.row} col={cell.col} />;
        if (cell.type === "goal") {
          return <Goal key={key} row={cell.row} col={cell.col} reduceMotion={reduceMotion} />;
        }
        if (cell.type === "gem") {
          return <Gem key={key} row={cell.row} col={cell.col} reduceMotion={reduceMotion} />;
        }
        if (cell.type === "soil") {
          return <Soil key={key} row={cell.row} col={cell.col} kind={cell.kind} />;
        }
        if (cell.type === "barn") {
          return <Barn key={key} row={cell.row} col={cell.col} reduceMotion={reduceMotion} />;
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
      {!reduceMotion ? (
        <Sparkles
          count={40}
          scale={[meta.cols + 4, 3, meta.rows + 4]}
          position={[cx, 1.4, cz]}
          size={1.6}
          speed={0.2}
          opacity={0.35}
          color="#9ec9ff"
        />
      ) : null}
    </>
  );
}

function cameraForGrid(rows, cols, topDown) {
  const span = Math.max(rows, cols, 3);
  const center = [(cols - 1) / 2, 0.3, (rows - 1) / 2];
  if (topDown) {
    const zoom = Math.max(18, Math.min(48, 155 / span));
    return {
      center,
      camera: { position: [center[0], 20, center[2] + 0.01], zoom, near: 0.1, far: 120 },
      minDistance: 4,
      maxDistance: 34,
    };
  }
  const distance = Math.max(6.2, span * 1.25);
  return {
    center,
    camera: {
      position: [center[0] + distance * 0.62, distance * 0.72, center[2] + distance * 0.82],
      fov: 34,
      near: 0.1,
      far: 120,
    },
    minDistance: 4,
    maxDistance: Math.max(22, span * 2.8),
  };
}

export default function GhostwalkScene({
  grid,
  hero,
  topDown = false,
  reduceMotion = false,
  language = "python",
  mode = "free",
}) {
  const prefs = readPrefs();
  const quiet = reduceMotion || prefs.reduceMotion;
  const theme = themeFor(language, {
    farm: mode === "farm",
    contrast: prefs.contrast,
  });
  PALETTE = theme.palette;
  THEME_SHAPES = theme.shapes;
  const rows = grid?.length || 3;
  const cols = (typeof grid?.[0] === "string" ? grid[0].length : grid?.[0]?.length) || 3;
  const framing = cameraForGrid(rows, cols, topDown);
  const borderGlow = theme.palette.floorGlow || "#7eb6ff";

  return (
    <div
      className="ghostwalk-canvas h-full min-h-[16rem] w-full overflow-hidden rounded-2xl border-2 shadow-[0_0_0_1px_rgba(126,182,255,0.18),0_18px_50px_rgba(6,12,28,0.55)]"
      style={{
        background: theme.palette.void,
        borderColor: `color-mix(in srgb, ${borderGlow} 55%, transparent)`,
      }}
    >
      <Canvas
        key={`${topDown ? "top" : "persp"}-${language}-${mode}`}
        shadows
        dpr={[1, 1.75]}
        gl={{ antialias: true, alpha: false }}
        orthographic={topDown}
        camera={framing.camera}
        aria-label={`${theme.id} Ghostwalk 3D world`}
      >
        <color attach="background" args={[theme.palette.void]} />
        <fog attach="fog" args={[theme.palette.fog, 12, 42]} />
        <WorldContents grid={grid} hero={hero} reduceMotion={quiet} />
        <OrbitControls
          enablePan={false}
          minDistance={framing.minDistance}
          maxDistance={framing.maxDistance}
          maxPolarAngle={topDown ? 0.01 : Math.PI / 2.25}
          target={framing.center}
        />
      </Canvas>
    </div>
  );
}
