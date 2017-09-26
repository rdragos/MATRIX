import os
import boto3
import json
import time


def create_key_pair():
    with open('ImagesDeployment/regions', 'r') as regions_file:
        regions = regions_file.readlines()

    regions = [r.strip() for r in regions]

    for region in regions:
        ec2 = boto3.resource('ec2', region_name=region)
        keypair = ec2.create_key_pair(KeyName='Matrix%s' % region.replace('-', ''))
        print(keypair.key_material)


def create_security_group():
    with open('ImagesDeployment/regions', 'r') as regions_file:
        regions = regions_file.readlines()

    regions = [r.strip() for r in regions]

    for region in regions:
        client = boto3.client('ec2', region_name=region)
        response = client.create_security_group(
            Description='Matrix system security group',
            GroupName='MatrixSG%s' % region.replace('-', ''),
            DryRun=False
        )
        sg_id = response['GroupId']
        ec2 = boto3.resource('ec2', region_name=region)
        security_group = ec2.SecurityGroup(sg_id)
        security_group.authorize_ingress(IpProtocol="tcp", CidrIp="0.0.0.0/0", FromPort=0, ToPort=65535)


def deploy_instances():
    with open('config.json') as data_file:
        data = json.load(data_file)
        machine_type = data['aWSInstType']
        price_bids = data['aWWSBidPrice']
        number_of_parties = data['numOfParties']
        amis_id = list(data['amis'].values())
        regions = list(data['regions'].values())

    if len(regions) > 1:
        number_of_instances = number_of_parties // len(regions)
    else:
        number_of_instances = number_of_parties

    for idx in range(len(regions)):
        client = boto3.client('ec2', region_name=regions[idx][:-1])
        client.request_spot_instances(
                DryRun=False,
                SpotPrice=price_bids,
                InstanceCount=number_of_instances,
                LaunchSpecification=
                {
                    'ImageId': amis_id[idx],
                    'KeyName': 'Matrix%s' % regions[idx].replace('-', '')[:-1],
                    'SecurityGroups': ['MatrixSG%s' % regions[idx].replace('-', '')[:-1]],
                    # 'SecurityGroupIds': ['sg-fa504d93'],
                    'InstanceType': machine_type,
                    'Placement':
                        {
                            'AvailabilityZone': regions[idx],
                        },
                },
        )

    time.sleep(120)

    get_network_details(regions)


def get_network_details(regions):
    with open('config.json') as data_file:
        data = json.load(data_file)
        protocol_name = data['protocol']
        os.system('mkdir -p ../%s' % protocol_name)

    instances_ids = list()
    public_ip_address = list()

    if len(regions) == 1:
        private_ip_address = list()

    for idx in range(len(regions)):
        client = boto3.client('ec2', region_name=regions[idx][:-1])
        response = client.describe_spot_instance_requests()

        for req_idx in range(len(response['SpotInstanceRequests'])):
            instances_ids.append(response['SpotInstanceRequests'][req_idx]['InstanceId'])

        # save instance_ids for experiment termination
        with open('instances_ids', 'w+') as ids_file:
            for instance_idx in range(len(instances_ids)):
                ids_file.write('%s\n' % instances_ids[instance_idx])

            ec2 = boto3.resource('ec2', region_name=regions[idx][:-1])
            instances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])

            for inst in instances:
                public_ip_address.append(inst.public_ip_address)
                if len(regions) == 1:
                    private_ip_address.append(inst.private_ip_address)

        # write public ips to file for fabric
        with open('public_ips', 'w+') as public_ip_file:
            for public_idx in range(len(public_ip_address)):
                public_ip_file.write('%s\n' % public_ip_address[public_idx])

        with open('parties.conf', 'w+') as private_ip_file:
            if len(regions) > 1:
                for private_idx in range(len(public_ip_address)):
                    private_ip_file.write('party_%s_ip = %s\n' % (private_idx, public_ip_address[private_idx]))
            else:
                for private_idx in range(len(private_ip_address)):
                    private_ip_file.write('party_%s_ip = %s\n' % (private_idx, private_ip_address[private_idx]))

            port_number = 8000

            for private_idx in range(len(public_ip_address)):
                private_ip_file.write('party_%s_port = %s\n' % (private_idx, port_number))


deploy_instances()
# create_security_group()
# create_key_pair()
