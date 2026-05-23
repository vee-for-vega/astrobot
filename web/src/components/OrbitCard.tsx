import type { Trajectory } from "../types";
import TopView from "./TopView";
import SideView from "./SideView";
import PlanetInfo from "./PlanetInfo";

type Props = {
  trajectory: Trajectory;
};

export default function OrbitCard({ trajectory }: Props) {
  const { planet, star, elements } = trajectory;
  return (
    <figure className="my-3 overflow-hidden rounded-lg border border-neutral-300 bg-white">
      <div className="grid grid-cols-2 divide-x divide-neutral-200">
        <div className="aspect-square">
          <TopView star={star} elements={elements} />
        </div>
        <div className="aspect-square">
          <SideView star={star} elements={elements} />
        </div>
      </div>
      <figcaption className="border-t border-neutral-200 bg-neutral-50 p-3">
        <PlanetInfo planet={planet} star={star} elements={elements} />
      </figcaption>
    </figure>
  );
}
