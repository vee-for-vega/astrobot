type Props = {
  size?: number;
  className?: string;
};

export default function RobotAvatar({ size = 40, className = "" }: Props) {
  return (
    <img
      src="/robot.png"
      alt="AstroBot"
      width={size}
      height={size}
      className={className}
      style={{ width: size, height: size, objectFit: "contain" }}
    />
  );
}
