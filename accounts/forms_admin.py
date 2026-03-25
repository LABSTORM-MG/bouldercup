"""
Admin-specific form classes and widgets.
Used by both accounts/admin.py (Django admin) and accounts/views/myadmin.py (custom admin).
"""

from django import forms
from django.utils.safestring import mark_safe

from .models import AdminMessage, Boulder, CountdownSettings, SiteSettings, SubmissionWindow
from django_ckeditor_5.widgets import CKEditor5Widget


class ColorPickerWidget(forms.TextInput):
    """Text input combined with a native color picker."""

    def __init__(self, attrs=None):
        default_attrs = {'style': 'width: 200px;'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def render(self, name, value, attrs=None, renderer=None):
        text_input = super().render(name, value, attrs, renderer)
        final_attrs = self.build_attrs(attrs, {'name': name})
        widget_id = final_attrs.get('id', f'id_{name}')

        color_picker_html = f'''
        <input type="color" id="{widget_id}_picker" style="margin-left: 5px; width: 50px; height: 30px; vertical-align: middle; cursor: pointer;" title="Farbe visuell auswählen">
        <script>
        (function() {{
            var textInput = document.getElementById('{widget_id}');
            var colorPicker = document.getElementById('{widget_id}_picker');

            function updateColorPicker() {{
                var value = textInput.value.trim();
                if (/^#[0-9A-Fa-f]{{6}}$/.test(value)) {{
                    colorPicker.value = value;
                }}
            }}

            colorPicker.addEventListener('input', function() {{
                textInput.value = colorPicker.value;
                textInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }});

            updateColorPicker();
            textInput.addEventListener('input', updateColorPicker);
            textInput.addEventListener('change', updateColorPicker);
        }})();
        </script>
        '''
        return mark_safe(text_input + color_picker_html)


class BoulderAdminForm(forms.ModelForm):
    color = forms.CharField(
        widget=ColorPickerWidget(),
        max_length=50,
        label="Farbe",
        help_text=(
            "Griff-/Tape-Farbe zur einfachen Zuordnung. Eingabe möglich als: "
            "Deutsche Namen (rot, blau, grün, türkis), Englische CSS-Namen (red, blue, hotpink), "
            "oder Hex-Codes (#ff0000, f00). Nicht-Standard-Farben werden automatisch auf die "
            "nächste CSS-Standardfarbe normalisiert."
        ),
    )

    class Meta:
        model = Boulder
        fields = "__all__"


class AdminMessageAdminForm(forms.ModelForm):
    background_color = forms.CharField(
        widget=forms.TextInput(attrs={"type": "color"}),
        label="Hintergrundfarbe",
        help_text="Hintergrundfarbe der Nachricht (Hex-Code).",
    )

    class Meta:
        model = AdminMessage
        fields = ("heading", "content", "background_color")


class SiteSettingsAdminForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = (
            "dashboard_heading",
            "greeting_enabled",
            "greeting_heading",
            "greeting_message",
            "help_text_content",
            "rulebook_content",
        )
        widgets = {
            "greeting_message": CKEditor5Widget(config_name="default"),
            "help_text_content": CKEditor5Widget(config_name="default"),
            "rulebook_content": CKEditor5Widget(config_name="default"),
        }


class CountdownSettingsAdminForm(forms.ModelForm):
    background_color = forms.CharField(
        widget=forms.TextInput(attrs={"type": "color"}),
        label="Hintergrundfarbe",
    )
    primary_color = forms.CharField(
        widget=forms.TextInput(attrs={"type": "color"}),
        label="Primärfarbe",
    )
    secondary_color = forms.CharField(
        widget=forms.TextInput(attrs={"type": "color"}),
        label="Sekundärfarbe",
    )

    class Meta:
        model = CountdownSettings
        fields = (
            "enabled",
            "countdown_end_time",
            "show_preview_button",
            "logo",
            "heading",
            "subtitle",
            "message",
            "background_image",
            "background_color",
            "primary_color",
            "secondary_color",
        )
        widgets = {
            "message": CKEditor5Widget(config_name="default"),
        }


class SubmissionWindowAdminForm(forms.ModelForm):
    submission_start = forms.SplitDateTimeField(
        required=False,
        label="Start",
        input_time_formats=["%H:%M", "%H:%M:%S"],
        widget=forms.SplitDateTimeWidget(
            date_attrs={"type": "date"},
            time_attrs={"type": "time"},
        ),
    )
    submission_end = forms.SplitDateTimeField(
        required=False,
        label="Ende",
        input_time_formats=["%H:%M", "%H:%M:%S"],
        widget=forms.SplitDateTimeWidget(
            date_attrs={"type": "date"},
            time_attrs={"type": "time"},
        ),
    )

    class Meta:
        model = SubmissionWindow
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("submission_start")
        end = cleaned_data.get("submission_end")
        if start and end and end <= start:
            raise forms.ValidationError(
                "Das Ende des Zeitfensters muss nach dem Start liegen."
            )
        return cleaned_data
