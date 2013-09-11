# Create your views here.
from models import *
from django.contrib.auth.decorators import login_required, permission_required
from django.template import RequestContext, Template, Context
from django.utils import simplejson
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.http import HttpResponse, Http404
from django.contrib.auth.models import Permission, User
from django.conf import settings
from django.core.context_processors import csrf
from django.shortcuts import render_to_response, get_object_or_404, redirect
from datetime import datetime, timedelta, date
import plistlib

#from forms import *

@login_required 
def index(request):
    # Get the current user's Business Units
    user = request.user
    if user.businessunit_set.count() == 1:
        # user only has one BU, redirect to it
        for bu in user.businessunit_set.all():
            return redirect('server.views.bu_dashboard', bu_id=bu.id)
            break
    else:
        # user has many BU's display them all in a friendly manner
        business_units = user.businessunit_set.all()
        # get the user level - if they're a global admin, show all of the machines. If not, show only the machines they have access to
        user_level = user.userprofile.level
        
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        three_months_ago = today - timedelta(days=90)
        machine_data = {}
        
        if user_level == 'GA':
            machine_data['checked_in_this_hour'] = Machine.objects.filter(last_checkin__gte=hour_ago).count()
            machine_data['checked_in_today'] = Machine.objects.filter(last_checkin__gte=today).count()
            machine_data['checked_in_this_week'] = Machine.objects.filter(last_checkin__gte=week_ago).count()
            machine_data['inactive_for_a_month'] = Machine.objects.filter(last_checkin__range=(three_months_ago, month_ago)).count()
            machine_data['inactive_for_three_months'] = Machine.objects.exclude(last_checkin__gte=three_months_ago).count()
        else:
            count = 0
            for bu in business_units:
                for machine_group in bu.machinegroup_set.all():
                    count = count + Machine.objects.filter(last_checkin__gte=hour_ago, machine_group=machine_group).count()
            machine_data['checked_in_this_hour'] = count
            count = 0
            for bu in business_units:
                for machine_group in bu.machinegroup_set.all():
                    count = count + Machine.objects.filter(last_checkin__gte=today, machine_group=machine_group).count()
            machine_data['checked_in_today'] = count
            count = 0
            for bu in business_units:
                for machine_group in bu.machinegroup_set.all():
                    count = count + Machine.objects.filter(last_checkin__gte=week_ago, machine_group=machine_group).count()
            machine_data['checked_in_this_week'] = count
            count = 0
            for bu in business_units:
                for machine_group in bu.machinegroup_set.all():
                    count = count + Machine.objects.filter(last_checkin__range=(three_months_ago, month_ago), machine_group=machine_group).count()
            machine_data['inactive_for_a_month'] = count
            count = 0
            for bu in business_units:
                for machine_group in bu.machinegroup_set.all():
                    count = count + Machine.objects.exclude(last_checkin__gte=three_months_ago).filter(machine_group=machine_group).count()
            machine_data['inactive_for_three_months'] = count
        c = {'user': request.user, 'business_units': business_units, 'machine_data': machine_data}
        return render_to_response('server/index.html', c, context_instance=RequestContext(request)) 

# New BU
   
# BU Dashboard
@login_required 
def bu_dashboard(request, bu_id):
    user = request.user
    user_level = user.userprofile.level
    business_unit = get_object_or_404(BusinessUnit, pk=bu_id)
    if business_unit not in user.businessunit_set.all():
        return redirect(index)
    # Get the groups within the Business Unit
    machine_groups = business_unit.machinegroup_set.all
    c = {'user': request.user, 'machine_groups': machine_groups, 'user_level': user_level}
    return render_to_response('server/bu_dashboard.html', c, context_instance=RequestContext(request))

# Machine Group Dashboard
@login_required 
def group_dashboard(request, group_id):
    # check user is allowed to access this
    user = request.user
    user_level = user.userprofile.level
    machine_group = get_object_or_404(MachineGroup, pk=group_id)
    business_unit = machine_group.business_unit
    if business_unit not in user.businessunit_set.all():
        return redirect(index)
        
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    three_months_ago = today - timedelta(days=90)
    
    machine_data = {}
    machine_data['checked_in_this_hour'] = Machine.objects.filter(last_checkin__gte=hour_ago, machine_group=machine_group).count()
    machine_data['checked_in_today'] = Machine.objects.filter(last_checkin__gte=today, machine_group=machine_group).count()
    machine_data['checked_in_this_week'] = Machine.objects.filter(last_checkin__gte=week_ago, machine_group=machine_group).count()
    machine_data['inactive_for_a_month'] = Machine.objects.filter(last_checkin__range=(three_months_ago, month_ago), machine_group=machine_group).count()
    machine_data['inactive_for_three_months'] = Machine.objects.exclude(last_checkin__gte=three_months_ago).filter(machine_group=machine_group).count()
    c = {'user': request.user, 'machine_group': machine_group, 'user_level': user_level, 'machine_data':machine_data, }
    return render_to_response('server/group_dashboard.html', c, context_instance=RequestContext(request))

# New Group

# Edit Group

# Delete Group

# Machine detail

# checkin
@csrf_exempt
def checkin(request):
    if request.method != 'POST':
        raise Http404
    
    data = request.POST
    key = data.get('key')
    serial = data.get('serial')
    business_unit = get_object_or_404(BusinessUnit, key=key)
    
    # look for serial number - if it doesn't exist, create one
    if serial:
        try:
            machine = Machine.objects.get(serial=serial)
        except Machine.DoesNotExist:
            machine = Machine(serial=serial)
    if machine:
        machine.hostname = data.get('name', '<NO NAME>')
        machine.last_checkin = datetime.now()
        if 'username' in data:
            machine.username = data.get('username')
        if 'base64bz2report' in data:
            machine.update_report(data.get('base64bz2report'))
        
        # extract machine data from the report
        report_data = machine.get_report()
        machine.report = report_data
        # find the matching group based on manifest
        if 'ManifestName' in report_data:
            manifest = report_data['ManifestName']
            machine_group = get_object_or_404(MachineGroup, manifest=manifest)
            machine.machine_group = machine_group
            machine.manifest = manifest
        if 'MachineInfo' in report_data:
            machine.operating_system = report_data['MachineInfo'].get(
                'os_vers', 'UNKNOWN')
        machine.hd_space = report_data.get('AvailableDiskSpace') or 0
        machine.munki_version = report_data.get('ManagedInstallVersion') or 0
        hwinfo = {}
        if 'SystemProfile' in report_data.get('MachineInfo', []):
            for profile in report_data['MachineInfo']['SystemProfile']:
                if profile['_dataType'] == 'SPHardwareDataType':
                    hwinfo = profile._items[0]
                    break
        if hwinfo:
            machine.memory = hwinfo.get('physical_memory') and hwinfo.get('physical_memory') or u'0'
            
        machine.save()
        return HttpResponse("Sal report submmitted for %s.\n" 
                            % data.get('name'))
        # return HttpResponse("Sal report submmitted for %s.\n" 
        #                     % report_data)