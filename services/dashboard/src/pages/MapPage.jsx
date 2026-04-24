import DashboardHeader from '@/components/header/DashboardHeader';
import StatsBar from '@/components/header/StatsBar';
import MapContainer from '@/components/map/MapContainer';
import DecisionSidebar from '@/components/sidebar/DecisionSidebar';

/**
 * Main map page — full-screen map with decision sidebar.
 * The map takes all available vertical space.
 */
export default function MapPage() {
  return (
    <div className="flex flex-col h-screen w-screen bg-navy-950 overflow-hidden">
      <DashboardHeader />
      <StatsBar />
      <div className="flex flex-1 overflow-hidden min-h-0">
        <MapContainer />
        <DecisionSidebar />
      </div>
    </div>
  );
}
