
from typing import List, Dict
from datetime import datetime, timedelta

class ScheduleOptimizer:
    @staticmethod
    def optimize_appointments(appointments: List[Dict], staff_availability: Dict) -> List[Dict]:
        """Optimize appointment scheduling to maximize efficiency"""
        # Sort appointments by duration (longest first)
        sorted_appts = sorted(appointments, 
                            key=lambda x: x.get('duration', 0), 
                            reverse=True)
        
        optimized = []
        staff_schedule = {staff_id: [] for staff_id in staff_availability}
        
        for appt in sorted_appts:
            best_slot = None
            best_staff = None
            min_gap = float('inf')
            
            for staff_id, schedule in staff_schedule.items():
                if not schedule:
                    best_slot = staff_availability[staff_id]['start']
                    best_staff = staff_id
                    break
                    
                # Find smallest gap that fits appointment
                for i in range(len(schedule)):
                    if i == 0:
                        gap_start = staff_availability[staff_id]['start']
                        gap_end = schedule[0]['start']
                    else:
                        gap_start = schedule[i-1]['end']
                        gap_end = schedule[i]['start']
                        
                    gap_duration = (gap_end - gap_start).total_seconds() / 60
                    if gap_duration >= appt['duration'] and gap_duration < min_gap:
                        min_gap = gap_duration
                        best_slot = gap_start
                        best_staff = staff_id
            
            if best_slot and best_staff:
                appt['start'] = best_slot
                appt['staff_id'] = best_staff
                optimized.append(appt)
                staff_schedule[best_staff].append(appt)
                
        return optimized
