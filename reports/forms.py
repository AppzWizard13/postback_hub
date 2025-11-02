
from django import forms
from .models import DailySelfAnalysis, TradingPlan

class DailySelfAnalysisForm(forms.ModelForm):
    class Meta:
        model = DailySelfAnalysis
        fields = [
            'health_check', 
            'mind_check', 
            'expectation_level', 
            'patience_level', 
            'previous_day_self_analysis', 
        ]
        widgets = {
            'health_check': forms.NumberInput(attrs={'min': 0, 'max': 100}),
            'mind_check': forms.NumberInput(attrs={'min': 0, 'max': 100}),
            'expectation_level': forms.NumberInput(attrs={'min': 0, 'max': 100}),
            'patience_level': forms.NumberInput(attrs={'min': 0, 'max': 100}),
            'previous_day_self_analysis': forms.NumberInput(attrs={'min': 0, 'max': 100}),
        }




class TradingPlanForm(forms.ModelForm):
    class Meta:
        model = TradingPlan
        fields = ['plan_name', 'initial_capital', 'expected_growth', 'no_of_weeks', 'average_weekly_gain', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'initial_capital': forms.NumberInput(attrs={'step': '0.01'}),
            'expected_growth': forms.NumberInput(attrs={'step': '0.01'}),
            'average_weekly_gain': forms.NumberInput(attrs={'step': '0.01'}),
        }
