"""
Main visualization script for altitude-maps project.

Creates temperature and climate visualizations based on altitude data.
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys
import io
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from data_sources import DataManager


class AltitudeVisualizer:
    """Creates visualizations of climate data by altitude."""
    
    def __init__(self, output_dir: str = "generated"):
        """
        Initialize the visualizer.
        
        Args:
            output_dir: Directory to save output visualizations
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.data_manager = DataManager()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Set style
        sns.set_style("darkgrid")
        plt.rcParams['figure.facecolor'] = 'white'
    
    def _get_output_path(self, description: str) -> Path:
        """
        Generate a timestamped output filename.
        
        Args:
            description: Description of the visualization
            
        Returns:
            Path for the output file
        """
        filename = f"{self.timestamp}_{description}.png"
        return self.output_dir / filename
        
    def create_3d_surface_plot(self, data: dict, save: bool = True) -> None:
        """
        Create a 3D surface plot of elevation with temperature overlay.
        
        Args:
            data: Dataset dictionary containing elevation and temperature
            save: Whether to save the plot
        """
        fig = plt.figure(figsize=(16, 12))
        ax = fig.add_subplot(111, projection='3d')
        
        # Create meshgrid
        X, Y = np.meshgrid(data['longitudes'], data['latitudes'])
        
        # Plot surface with temperature as color
        surf = ax.plot_surface(
            X, Y, data['elevation'],
            facecolors=plt.cm.RdYlBu_r((data['temperature'] - data['temperature'].min()) / 
                                       (data['temperature'].max() - data['temperature'].min())),
            linewidth=0,
            antialiased=True,
            alpha=0.9
        )
        
        ax.set_xlabel('Longitude', fontsize=12, labelpad=10)
        ax.set_ylabel('Latitude', fontsize=12, labelpad=10)
        ax.set_zlabel('Elevation (m)', fontsize=12, labelpad=10)
        ax.set_title('3D Elevation Map with Temperature Gradient\n', 
                     fontsize=16, fontweight='bold', pad=20)
        
        # Add a color bar
        m = plt.cm.ScalarMappable(cmap=plt.cm.RdYlBu_r)
        m.set_array([data['temperature'].min(), data['temperature'].max()])
        cbar = plt.colorbar(m, ax=ax, shrink=0.5, aspect=5)
        cbar.set_label('Temperature (°C)', rotation=270, labelpad=20, fontsize=11)
        
        # Better viewing angle
        ax.view_init(elev=25, azim=45)
        
        plt.tight_layout()
        
        if save:
            output_path = self._get_output_path("3d_elevation_temperature_map")
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"✓ Saved: {output_path}")
        
        plt.show()
        
    def create_contour_plot(self, data: dict, save: bool = True) -> None:
        """
        Create contour plots of elevation and temperature.
        
        Args:
            data: Dataset dictionary
            save: Whether to save the plot
        """
        fig, axes = plt.subplots(1, 2, figsize=(18, 7))
        
        # Elevation contour
        X, Y = np.meshgrid(data['longitudes'], data['latitudes'])
        
        # Elevation
        contour1 = axes[0].contourf(X, Y, data['elevation'], levels=20, cmap='terrain')
        axes[0].contour(X, Y, data['elevation'], levels=10, colors='black', 
                       alpha=0.3, linewidths=0.5)
        axes[0].set_xlabel('Longitude', fontsize=12)
        axes[0].set_ylabel('Latitude', fontsize=12)
        axes[0].set_title('Elevation Map', fontsize=14, fontweight='bold')
        cbar1 = plt.colorbar(contour1, ax=axes[0])
        cbar1.set_label('Elevation (m)', rotation=270, labelpad=20)
        
        # Temperature
        contour2 = axes[1].contourf(X, Y, data['temperature'], levels=20, cmap='RdYlBu_r')
        axes[1].contour(X, Y, data['temperature'], levels=10, colors='black', 
                       alpha=0.3, linewidths=0.5)
        axes[1].set_xlabel('Longitude', fontsize=12)
        axes[1].set_ylabel('Latitude', fontsize=12)
        axes[1].set_title('Temperature Distribution', fontsize=14, fontweight='bold')
        cbar2 = plt.colorbar(contour2, ax=axes[1])
        cbar2.set_label('Temperature (°C)', rotation=270, labelpad=20)
        
        plt.suptitle('Elevation and Temperature Contour Maps', 
                    fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()
        
        if save:
            output_path = self._get_output_path("elevation_temperature_contour_maps")
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"✓ Saved: {output_path}")
        
        plt.show()
        
    def create_relationship_plot(self, data: dict, save: bool = True) -> None:
        """
        Create a scatter plot showing temperature vs elevation relationship.
        
        Args:
            data: Dataset dictionary
            save: Whether to save the plot
        """
        # Flatten the arrays
        elevation_flat = data['elevation'].flatten()
        temperature_flat = data['temperature'].flatten()
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Create hexbin plot for density
        hexbin = ax.hexbin(elevation_flat, temperature_flat, gridsize=30, 
                          cmap='YlOrRd', mincnt=1)
        
        # Add trend line
        z = np.polyfit(elevation_flat, temperature_flat, 1)
        p = np.poly1d(z)
        elevation_sorted = np.sort(elevation_flat)
        ax.plot(elevation_sorted, p(elevation_sorted), "b--", 
               linewidth=2, label=f'Trend: T = {z[0]:.4f}·h + {z[1]:.2f}')
        
        ax.set_xlabel('Elevation (m)', fontsize=13, fontweight='bold')
        ax.set_ylabel('Temperature (°C)', fontsize=13, fontweight='bold')
        ax.set_title('Temperature vs Elevation Relationship\n', 
                    fontsize=16, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        
        cbar = plt.colorbar(hexbin, ax=ax)
        cbar.set_label('Density', rotation=270, labelpad=20)
        
        # Add statistics text
        stats_text = f'Points: {len(elevation_flat):,}\n'
        stats_text += f'Lapse rate: {-z[0]*1000:.2f}°C/1000m'
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
               fontsize=10, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        
        if save:
            output_path = self._get_output_path("temperature_vs_elevation_scatter")
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"✓ Saved: {output_path}")
        
        plt.show()
        
    def create_all_visualizations(self, data: dict) -> None:
        """
        Create all visualization types.
        
        Args:
            data: Dataset dictionary
        """
        print("\n=== Creating Visualizations ===")
        print("This may take a moment...\n")
        
        self.create_contour_plot(data)
        self.create_relationship_plot(data)
        self.create_3d_surface_plot(data)
        
        print(f"\n✓ All visualizations saved to: {self.output_dir}/")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Create altitude-based climate visualizations'
    )
    parser.add_argument(
        '--output', '-o',
        default='generated',
        help='Output directory for visualizations'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Display plots without saving'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  ALTITUDE MAPS - Climate Visualization Tool")
    print("=" * 60)
    
    # Initialize visualizer
    visualizer = AltitudeVisualizer(output_dir=args.output)
    
    # Get sample data
    print("\nGenerating sample dataset...")
    data = visualizer.data_manager.create_sample_dataset()
    print(f"✓ Dataset ready: {data['elevation'].shape[0]}×{data['elevation'].shape[1]} grid")
    
    # Create visualizations
    visualizer.create_all_visualizations(data)
    
    print("\n" + "=" * 60)
    print("  Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

