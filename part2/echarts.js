// Only the pieces the charts use, so the inlined bundle stays a fraction of full ECharts.
import * as echarts from 'echarts/core';
import { CustomChart, LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, DataZoomComponent, MarkLineComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([CustomChart, LineChart, GridComponent, TooltipComponent, DataZoomComponent, MarkLineComponent, LegendComponent, CanvasRenderer]);
window.echarts = echarts;
