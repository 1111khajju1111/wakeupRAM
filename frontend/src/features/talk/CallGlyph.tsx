export type GlyphPhase = "idle" | "listening" | "processing" | "speaking";

/**
 * A small original dot-grid glyph representing Ram's presence during a
 * call — section 13 asks for "an original dot/glyph visual", explicitly
 * not a copy of proprietary Nothing OS assets (section 15). This is plain
 * static markup; all animation is CSS-driven by the `glyph--{phase}` class
 * (see global.css) so the behavior differences between listening/
 * processing/speaking stay in one place and stay restrained, per section
 * 15's "restrained animation" guidance.
 */
export function CallGlyph({ phase }: { phase: GlyphPhase }) {
  const dots = Array.from({ length: 9 }, (_, i) => i);
  return (
    <div className={`call-glyph call-glyph--${phase}`} role="img" aria-label={phase}>
      {dots.map((i) => (
        <span key={i} className="call-glyph__dot" style={{ animationDelay: `${(i % 3) * 0.15}s` }} />
      ))}
    </div>
  );
}
