type SurfaceProps = {
  children: React.ReactNode;
  className?: string;
};

export default function Surface({ children, className = "" }: SurfaceProps) {
  return (
    <div className={`app-surface min-h-screen ${className}`.trim()}>
      {children}
    </div>
  );
}
