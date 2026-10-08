import { creativeHouses } from "../../src/creative-houses";

export function CreativeIslandScene({ ariaHidden = false }: { ariaHidden?: boolean }) {
  return <div className="creative-book-canvas kids-3d-scene kids-book-fallback" aria-hidden={ariaHidden}>
    <img className="creative-book-background kids-book-fallback__image" src="/creative-book-world.png" alt="打开的 AI 创作书与知识河" />
    <nav className="creative-book-overlay" aria-label="创作小屋">
      {creativeHouses.map((house) => <a key={house.id} href={house.href} className={`creative-book-overlay__link creative-book-overlay__link--${house.id}`}>
        <span className="creative-book-overlay__icon">{house.icon}</span><span>{house.label}</span><small>{house.hint}</small>
      </a>)}
    </nav>
  </div>;
}
