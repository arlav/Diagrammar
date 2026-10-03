import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import * as THREE from "three";
import App from "./App";
import "./styles.css";

// the model is in metres with Z up, as in the grammar
THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
