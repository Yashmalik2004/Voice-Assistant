import { VoiceWidget } from "./VoiceWidget";
import "./widget.css";
import "./demo.css";

// Standalone demo page hosting the Voice Assistant embeddable widget (spec section 6.1).
export default function App() {
  return (
    <main className="demo-page">
      <div className="demo-hero">
        <h1>Voice Assistant</h1>
        <p>Real-time voice support for your orders. Click start and just talk.</p>
      </div>
      <VoiceWidget />
    </main>
  );
}
